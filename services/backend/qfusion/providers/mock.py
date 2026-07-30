"""Deterministic, network-free provider used by CI and local demonstrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

from qfusion.domain import DataSourceRecord, Market, QualityFlag
from qfusion.providers.contracts import (
    AssetType,
    BarHistoryWindow,
    DataDeliveryQuality,
    DataInterval,
    MarketDataAccess,
    MarketDataCapability,
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
    market_data_capabilities=(
        MarketDataCapability(
            market=Market.HK,
            operation=ProviderOperation.BARS,
            supported_intervals=(DataInterval.MINUTE_1, DataInterval.DAY_1),
            bar_history=(
                BarHistoryWindow(
                    interval=DataInterval.MINUTE_1,
                    historical_start=date(2000, 1, 1),
                ),
                BarHistoryWindow(
                    interval=DataInterval.DAY_1,
                    historical_start=date(2000, 1, 1),
                ),
            ),
        ),
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.BARS,
            supported_intervals=(DataInterval.MINUTE_1, DataInterval.DAY_1),
            bar_history=(
                BarHistoryWindow(
                    interval=DataInterval.MINUTE_1,
                    historical_start=date(2000, 1, 1),
                ),
                BarHistoryWindow(
                    interval=DataInterval.DAY_1,
                    historical_start=date(2000, 1, 1),
                ),
            ),
        ),
    ),
    supports_options=False,
    supports_fundamentals=False,
    supports_news=False,
    supports_filings=False,
    supports_streaming=False,
    rate_limit=(),
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
        MarketDataAccess(
            market=Market.HK,
            operation=ProviderOperation.BARS,
            data_quality=DataDeliveryQuality.SYNTHETIC_MOCK,
        ),
        MarketDataAccess(
            market=Market.US,
            operation=ProviderOperation.BARS,
            data_quality=DataDeliveryQuality.SYNTHETIC_MOCK,
        ),
    ),
    notes=("No network, credentials, or real market data.",),
)
validate_provider_access(_MOCK_CAPABILITY, _MOCK_ACCESS)


class SyntheticMockMarketDataProvider:
    """Filter prevalidated synthetic facts behind the production adapter boundary."""

    def __init__(
        self,
        records: Sequence[DataSourceRecord],
        instrument_map: Mapping[UUID, tuple[str, Market]],
    ) -> None:
        if not instrument_map:
            raise ValueError("instrument_map must not be empty")

        normalized_map: dict[UUID, tuple[str, Market]] = {}
        for instrument_id, mapping in instrument_map.items():
            provider_instrument_id, market = mapping
            if (
                not provider_instrument_id
                or provider_instrument_id != provider_instrument_id.strip()
            ):
                raise ValueError("provider instrument identifiers must be non-empty and trimmed")
            if not isinstance(market, Market):
                raise ValueError("instrument markets must use the canonical Market enum")
            normalized_map[instrument_id] = (provider_instrument_id, market)

        provider_instrument_ids = [
            provider_instrument_id
            for provider_instrument_id, _market in normalized_map.values()
        ]
        if len(provider_instrument_ids) != len(set(provider_instrument_ids)):
            raise ValueError("provider instrument identifiers must be unique")

        selected = tuple(record.model_copy(deep=True) for record in records)
        fact_ids = [record.fact_id for record in selected]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("synthetic records must have unique fact_id values")
        for record in selected:
            self._validate_record(record, normalized_map)

        self._instrument_map = normalized_map
        self._records = tuple(
            sorted(selected, key=lambda item: (item.event_time, str(item.fact_id)))
        )

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
        instrument_mapping = self._instrument_map.get(request.instrument_id)
        if instrument_mapping is None:
            raise LookupError("instrument_id is not mapped for the synthetic provider")
        expected_provider_id, expected_market = instrument_mapping
        if request.market is not expected_market:
            raise ValueError("request market does not match the internal instrument mapping")
        if request.provider_instrument_id != expected_provider_id:
            raise ValueError(
                "provider_instrument_id does not match the internal instrument mapping"
            )

        return tuple(
            record.model_copy(deep=True)
            for record in self._records
            if record.instrument_id == request.instrument_id
            and record.fact_type == request.fact_type
            and request.start <= record.event_time <= request.end
            and record.available_at <= request.decision_time
        )

    @staticmethod
    def _validate_record(
        record: DataSourceRecord,
        instrument_map: Mapping[UUID, tuple[str, Market]],
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
