"""Deterministic, network-free provider used by CI and local demonstrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

from qfusion.domain import DataSourceRecord, Market, QualityFlag
from qfusion.providers.contracts import (
    AssetType,
    DataDeliveryQuality,
    DataInterval,
    MarketDataAccess,
    ProviderAccessProfile,
    ProviderAccessStatus,
    ProviderBarRequest,
    ProviderCapability,
    ProviderOperation,
    validate_bar_request,
    validate_provider_access,
)

_MOCK_CAPABILITY: Final = ProviderCapability(
    provider_name="qfusion-synthetic-mock",
    provider_version="1.0.0",
    supported_markets=(Market.HK, Market.US),
    supported_asset_types=(
        AssetType.STOCK,
        AssetType.ADR,
        AssetType.ETF,
        AssetType.SECTOR_ETF,
    ),
    supported_intervals=(DataInterval.MINUTE_1, DataInterval.DAY_1),
    supports_realtime=False,
    supports_premarket=False,
    supports_afterhours=False,
    supports_options=False,
    supports_fundamentals=False,
    supports_news=False,
    supports_filings=False,
    supports_streaming=False,
    rate_limit=(),
    historical_start=date(2000, 1, 1),
    venue_scope="synthetic-us-hk",
    quality_level="synthetic",
    license_scope="test-only",
    operations=(ProviderOperation.BARS,),
)
_MOCK_ACCESS: Final = ProviderAccessProfile(
    provider_name=_MOCK_CAPABILITY.provider_name,
    provider_version=_MOCK_CAPABILITY.provider_version,
    status=ProviderAccessStatus.ENABLED,
    access_scope="synthetic-test-only",
    verified_at=datetime(2026, 1, 1, tzinfo=UTC),
    enabled_operations=(ProviderOperation.BARS,),
    market_data_quality=(
        MarketDataAccess(market=Market.HK, data_quality=DataDeliveryQuality.SYNTHETIC_MOCK),
        MarketDataAccess(market=Market.US, data_quality=DataDeliveryQuality.SYNTHETIC_MOCK),
    ),
    notes=("No network, credentials, or real market data.",),
)
validate_provider_access(_MOCK_CAPABILITY, _MOCK_ACCESS)


class SyntheticMockMarketDataProvider:
    """Filter prevalidated synthetic facts behind the production adapter boundary."""

    def __init__(
        self,
        records: Sequence[DataSourceRecord],
        instrument_map: Mapping[UUID, str],
    ) -> None:
        if not instrument_map:
            raise ValueError("instrument_map must not be empty")

        normalized_map: dict[UUID, str] = {}
        for instrument_id, provider_instrument_id in instrument_map.items():
            if (\n                not provider_instrument_id\n                or provider_instrument_id != provider_instrument_id.strip()\n            ):
                raise ValueError("provider instrument identifiers must be non-empty and trimmed")
            normalized_map[instrument_id] = provider_instrument_id
        if len(normalized_map.values()) != len(set(normalized_map.values())):
            raise ValueError("provider instrument identifiers must be unique")

        selected = tuple(records)
        fact_ids = [record.fact_id for record in selected]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("synthetic records must have unique fact_id values")
        for record in selected:
            self._validate_record(record, normalized_map)

        self._instrument_map = normalized_map
        self._records = tuple(\n            sorted(selected, key=lambda item: (item.event_time, str(item.fact_id)))\n        )

    @property
    def capability(self) -> ProviderCapability:
        """Return the fixed technical capability of the synthetic adapter."""

        return _MOCK_CAPABILITY

    @property
    def access_profile(self) -> ProviderAccessProfile:
        """Return explicit synthetic-only access quality."""

        return _MOCK_ACCESS

    async def get_bars(self, request: ProviderBarRequest) -> Sequence[DataSourceRecord]:
        """Return deterministic, scoped, Point-in-Time-safe synthetic bars."""

        validate_bar_request(self.capability, self.access_profile, request)
        expected_provider_id = self._instrument_map.get(request.instrument_id)
        if expected_provider_id is None:
            raise LookupError("instrument_id is not mapped for the synthetic provider")
        if request.provider_instrument_id != expected_provider_id:
            raise ValueError(\n                "provider_instrument_id does not match the internal instrument mapping"\n            )

        return tuple(
            record
            for record in self._records
            if record.instrument_id == request.instrument_id
            and record.fact_type == request.fact_type
            and request.start <= record.event_time <= request.end
            and record.available_at <= request.decision_time
        )

    @staticmethod
    def _validate_record(
        record: DataSourceRecord,
        instrument_map: Mapping[UUID, str],
    ) -> None:
        if record.instrument_id is None or record.instrument_id not in instrument_map:
            raise ValueError("synthetic bar record must reference a mapped instrument_id")
        if record.fact_type not in {"daily_bar", "minute_bar"}:
            raise ValueError("synthetic market-data provider accepts only bar facts")
        if record.source != _MOCK_CAPABILITY.provider_name:
            raise ValueError("synthetic record source does not match provider identity")
        if record.provider_version != _MOCK_CAPABILITY.provider_version:
            raise ValueError("synthetic record provider_version does not match capability")
        if record.source_quality_level != _MOCK_CAPABILITY.quality_level:
            raise ValueError("synthetic record quality level does not match capability")
        if record.venue_scope != _MOCK_CAPABILITY.venue_scope:
            raise ValueError("synthetic record venue scope does not match capability")
        if record.license_scope != _MOCK_CAPABILITY.license_scope:
            raise ValueError("synthetic record license scope does not match capability")
        if record.quality_flag is not QualityFlag.SYNTHETIC_MOCK:
            raise ValueError("synthetic record must be explicitly marked SYNTHETIC_MOCK")
