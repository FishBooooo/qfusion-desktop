"""SEC EDGAR filing metadata Adapter with injectable network transport."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Final

from qfusion.domain import DataSourceRecord, Market
from qfusion.providers.contracts import (
    AssetType,
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
from qfusion.providers.sec.contracts import (
    SecFilingRequest,
    validate_sec_filing_request,
)
from qfusion.providers.sec.parser import parse_sec_submissions
from qfusion.providers.sec.transport import SecJsonTransport

_SEC_CAPABILITY: Final = ProviderCapability(
    provider_name="sec-edgar",
    provider_version="1.0.0",
    supported_markets=(Market.US,),
    supported_asset_types=(
        AssetType.ADR,
        AssetType.ETF,
        AssetType.SECTOR_ETF,
        AssetType.STOCK,
    ),
    market_data_capabilities=(),
    supports_options=False,
    supports_fundamentals=False,
    supports_news=False,
    supports_filings=True,
    supports_streaming=False,
    rate_limit=(
        RateLimitPolicy(
            operation=ProviderOperation.FILINGS,
            max_requests=5,
            window_seconds=1,
            max_concurrent=1,
        ),
    ),
    venue_scope="US-SEC-EDGAR",
    quality_level="official-public-filings",
    license_scope="public-government-content",
    usage_policy=ProviderUsagePolicy(
        terms_url="https://www.sec.gov/about/webmaster-frequently-asked-questions",
        terms_checked_at=date(2026, 7, 30),
        personal_research=ProviderUsageStatus.ALLOWED,
        local_cache=ProviderUsageStatus.ALLOWED,
        persistent_storage=ProviderUsageStatus.ALLOWED,
        private_display=ProviderUsageStatus.ALLOWED,
        public_display=ProviderUsageStatus.UNVERIFIED,
        commercial_use=ProviderUsageStatus.UNVERIFIED,
        redistribution=ProviderUsageStatus.UNVERIFIED,
        model_processing=ProviderUsageStatus.UNVERIFIED,
        attribution_required=True,
        attribution_text="Source: U.S. Securities and Exchange Commission EDGAR.",
        required_notices=(
            "Do not imply SEC endorsement; preserve filing source and provenance.",
        ),
    ),
    operations=(ProviderOperation.FILINGS,),
)
_SEC_ACCESS: Final = ProviderAccessProfile(
    provider_name=_SEC_CAPABILITY.provider_name,
    provider_version=_SEC_CAPABILITY.provider_version,
    status=ProviderAccessStatus.ENABLED,
    access_scope="public-no-authentication",
    verified_at=datetime(2026, 7, 30, tzinfo=UTC),
    enabled_operations=(ProviderOperation.FILINGS,),
    market_data_quality=(),
    notes=(
        "No API key or account entitlement is required.",
        "Runtime requests still require a declared User-Agent.",
    ),
)
validate_provider_access(_SEC_CAPABILITY, _SEC_ACCESS)


class SecEdgarProvider:
    """Convert SEC submissions metadata into vendor-neutral filing facts."""

    def __init__(self, transport: SecJsonTransport) -> None:
        self._transport = transport

    @property
    def capability(self) -> ProviderCapability:
        return _SEC_CAPABILITY

    @property
    def access_profile(self) -> ProviderAccessProfile:
        return _SEC_ACCESS

    async def get_filings(
        self,
        request: SecFilingRequest,
    ) -> Sequence[DataSourceRecord]:
        """Return newly observed filing facts for persistence before snapshot queries."""

        validate_sec_filing_request(self.capability, self.access_profile, request)
        validate_provider_usage(
            self.capability,
            ProviderUsage.PERSISTENT_STORAGE,
        )
        response = await self._transport.get_submissions(request.cik)
        return parse_sec_submissions(
            response.payload,
            request,
            received_at=response.received_at,
            ingested_at=response.received_at,
        )
