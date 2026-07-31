"""BLS Public Data API v1 macro-series Adapter with conservative PIT semantics."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Final

from qfusion.domain import DataSourceRecord, Market
from qfusion.providers.bls.contracts import (
    BlsSeriesRequest,
    validate_bls_series_request,
)
from qfusion.providers.bls.parser import parse_bls_series
from qfusion.providers.bls.transport import BlsJsonTransport
from qfusion.providers.contracts import (
    ProviderAccessProfile,
    ProviderAccessStatus,
    ProviderCapability,
    ProviderOperation,
    ProviderUsage,
    ProviderUsagePolicy,
    ProviderUsageStatus,
    RateLimitPolicy,
    validate_provider_access,
    validate_provider_usage,
)

_BLS_CAPABILITY: Final = ProviderCapability(
    provider_name="bls-public-data-v1",
    provider_version="1.0.0",
    supported_markets=(Market.US,),
    supported_asset_types=(),
    market_data_capabilities=(),
    supports_options=False,
    supports_fundamentals=False,
    supports_news=False,
    supports_filings=False,
    supports_streaming=False,
    rate_limit=(
        RateLimitPolicy(
            operation=ProviderOperation.MACRO_SERIES,
            max_requests=25,
            window_seconds=86_400,
            max_concurrent=1,
        ),
    ),
    venue_scope="US-BLS",
    quality_level="official-published-macro-series",
    license_scope="bls-api-secondary-use-with-attribution",
    usage_policy=ProviderUsagePolicy(
        terms_url="https://www.bls.gov/developers/termsOfService.htm",
        terms_checked_at=date(2026, 7, 31),
        personal_research=ProviderUsageStatus.ALLOWED,
        local_cache=ProviderUsageStatus.ALLOWED,
        persistent_storage=ProviderUsageStatus.ALLOWED,
        private_display=ProviderUsageStatus.ALLOWED,
        public_display=ProviderUsageStatus.UNVERIFIED,
        commercial_use=ProviderUsageStatus.UNVERIFIED,
        redistribution=ProviderUsageStatus.UNVERIFIED,
        model_processing=ProviderUsageStatus.ALLOWED,
        attribution_required=True,
        attribution_text="Source: U.S. Bureau of Labor Statistics Public Data API.",
        required_notices=(
            "BLS cannot vouch for derived data or analyses after retrieval.",
            "Record the BLS retrieval date with every stored observation.",
        ),
    ),
    operations=(ProviderOperation.MACRO_SERIES,),
)
_BLS_ACCESS: Final = ProviderAccessProfile(
    provider_name=_BLS_CAPABILITY.provider_name,
    provider_version=_BLS_CAPABILITY.provider_version,
    status=ProviderAccessStatus.ENABLED,
    access_scope="public-v1-no-registration",
    verified_at=datetime(2026, 7, 31, tzinfo=UTC),
    enabled_operations=(ProviderOperation.MACRO_SERIES,),
    market_data_quality=(),
    notes=(
        "Public Data API v1 requires no registration key.",
        "Unregistered v1 requests are limited to 25 series and 10 years.",
        "Version 1 exposes no catalog metadata or historical vintages.",
        "Version 1 can lag the BLS publication page by one day.",
    ),
)
validate_provider_access(_BLS_CAPABILITY, _BLS_ACCESS)


class BlsPublicDataProvider:
    """Convert BLS v1 monthly data into immutable first-observed macro facts."""

    def __init__(self, transport: BlsJsonTransport) -> None:
        self._transport = transport

    @property
    def capability(self) -> ProviderCapability:
        return _BLS_CAPABILITY

    @property
    def access_profile(self) -> ProviderAccessProfile:
        return _BLS_ACCESS

    async def get_series(
        self,
        request: BlsSeriesRequest,
    ) -> Sequence[DataSourceRecord]:
        """Return first-observed monthly facts for persistence and model snapshots."""

        validate_bls_series_request(self.capability, self.access_profile, request)
        validate_provider_usage(self.capability, ProviderUsage.PERSISTENT_STORAGE)
        validate_provider_usage(self.capability, ProviderUsage.MODEL_PROCESSING)
        response = await self._transport.get_series(request)
        return parse_bls_series(
            response.payload,
            request,
            received_at=response.received_at,
            ingested_at=response.received_at,
        )
