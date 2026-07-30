"""Vendor-neutral provider capabilities, account access, and request contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from qfusion.domain import MARKET_TIMEZONES, Market

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class AssetType(StrEnum):
    """Canonical first-phase asset classes exposed to provider adapters."""

    STOCK = "stock"
    ADR = "adr"
    ETF = "etf"
    SECTOR_ETF = "sector_etf"
    BASKET = "basket"


class DataInterval(StrEnum):
    """Canonical bar intervals independent of vendor spellings."""

    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    DAY_1 = "1d"


_DATA_INTERVAL_ORDER = {
    interval: index for index, interval in enumerate(DataInterval)
}


class ProviderOperation(StrEnum):
    """Operations an adapter may technically implement or an account may enable."""

    INSTRUMENT_SEARCH = "instrument_search"
    INSTRUMENT_LOOKUP = "instrument_lookup"
    SYMBOL_HISTORY = "symbol_history"
    BARS = "bars"
    QUOTES = "quotes"
    TRADES = "trades"
    STREAM_QUOTES = "stream_quotes"
    FUNDAMENTALS = "fundamentals"
    ESTIMATES = "estimates"
    CORPORATE_ACTIONS = "corporate_actions"
    NEWS = "news"
    FILINGS = "filings"
    EVENTS = "events"
    OPTION_CHAIN = "option_chain"
    OPTION_SNAPSHOT = "option_snapshot"
    SHORT_INTEREST = "short_interest"
    SHORT_VOLUME = "short_volume"
    SOUTHBOUND_FLOW = "southbound_flow"


_MARKET_DATA_OPERATIONS = frozenset(
    {
        ProviderOperation.BARS,
        ProviderOperation.QUOTES,
        ProviderOperation.TRADES,
        ProviderOperation.STREAM_QUOTES,
    }
)


class DataDeliveryQuality(StrEnum):
    """Observed account-level delivery quality, not a vendor-wide promise."""

    REALTIME = "REALTIME"
    DELAYED = "DELAYED"
    END_OF_DAY = "END_OF_DAY"
    HISTORICAL = "HISTORICAL"
    SYNTHETIC_MOCK = "SYNTHETIC_MOCK"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderAccessStatus(StrEnum):
    """Whether an account access profile was actually verified."""

    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    UNVERIFIED = "UNVERIFIED"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("provider timestamps must be timezone-aware")
    return value.astimezone(UTC)


class ProviderContract(BaseModel):
    """Immutable base for values crossing the provider boundary."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class RateLimitPolicy(ProviderContract):
    """One documented request budget for one provider operation."""

    operation: ProviderOperation
    max_requests: int = Field(ge=1)
    window_seconds: int = Field(ge=1)
    max_concurrent: int | None = Field(default=None, ge=1)


class BarHistoryWindow(ProviderContract):
    """Earliest available bar date for one exact interval."""

    interval: DataInterval
    historical_start: date


class MarketDataCapability(ProviderContract):
    """Technical capability for one exact market and market-data operation."""

    market: Market
    operation: ProviderOperation
    supported_intervals: tuple[DataInterval, ...] = ()
    bar_history: tuple[BarHistoryWindow, ...] = ()
    supports_realtime: bool = False
    supports_premarket: bool = False
    supports_afterhours: bool = False

    @field_validator("supported_intervals")
    @classmethod
    def normalize_intervals(
        cls,
        values: tuple[DataInterval, ...],
    ) -> tuple[DataInterval, ...]:
        if len(values) != len(set(values)):
            raise ValueError("supported_intervals must be unique")
        return tuple(sorted(values, key=_DATA_INTERVAL_ORDER.__getitem__))

    @field_validator("bar_history")
    @classmethod
    def normalize_bar_history(
        cls,
        values: tuple[BarHistoryWindow, ...],
    ) -> tuple[BarHistoryWindow, ...]:
        intervals = [value.interval for value in values]
        if len(intervals) != len(set(intervals)):
            raise ValueError("bar_history must contain at most one start per interval")
        return tuple(
            sorted(
                values,
                key=lambda item: _DATA_INTERVAL_ORDER[item.interval],
            )
        )

    @model_validator(mode="after")
    def validate_market_data_capability(self) -> Self:
        if self.operation not in _MARKET_DATA_OPERATIONS:
            raise ValueError("market data capability requires a market-data operation")
        if self.operation is ProviderOperation.BARS and not self.supported_intervals:
            raise ValueError("bars capability requires supported_intervals")
        if self.operation is not ProviderOperation.BARS and (
            self.supported_intervals or self.bar_history
        ):
            raise ValueError(
                "only bars capability may declare supported_intervals or bar_history"
            )
        if any(
            window.interval not in self.supported_intervals
            for window in self.bar_history
        ):
            raise ValueError("bar_history references an unsupported interval")
        return self


class ProviderCapability(ProviderContract):
    """Versioned technical capability declared by an adapter implementation."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    provider_name: NonEmptyText
    provider_version: NonEmptyText
    supported_markets: tuple[Market, ...]
    supported_asset_types: tuple[AssetType, ...]
    market_data_capabilities: tuple[MarketDataCapability, ...] = ()
    supports_options: bool
    supports_fundamentals: bool
    supports_news: bool
    supports_filings: bool
    supports_streaming: bool
    rate_limit: tuple[RateLimitPolicy, ...] = ()
    venue_scope: NonEmptyText
    quality_level: NonEmptyText
    license_scope: NonEmptyText
    operations: tuple[ProviderOperation, ...]

    @field_validator("supported_markets")
    @classmethod
    def normalize_markets(cls, values: tuple[Market, ...]) -> tuple[Market, ...]:
        if not values:
            raise ValueError("supported_markets must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("supported_markets must be unique")
        return tuple(sorted(values, key=lambda item: item.value))

    @field_validator("supported_asset_types")
    @classmethod
    def normalize_asset_types(cls, values: tuple[AssetType, ...]) -> tuple[AssetType, ...]:
        if not values:
            raise ValueError("supported_asset_types must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("supported_asset_types must be unique")
        return tuple(sorted(values, key=lambda item: item.value))

    @field_validator("market_data_capabilities")
    @classmethod
    def normalize_market_data_capabilities(
        cls,
        values: tuple[MarketDataCapability, ...],
    ) -> tuple[MarketDataCapability, ...]:
        keys = [(value.market, value.operation) for value in values]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "market_data_capabilities must contain at most one entry "
                "per market and operation"
            )
        return tuple(
            sorted(
                values,
                key=lambda item: (item.market.value, item.operation.value),
            )
        )

    @field_validator("operations")
    @classmethod
    def normalize_operations(
        cls,
        values: tuple[ProviderOperation, ...],
    ) -> tuple[ProviderOperation, ...]:
        if not values:
            raise ValueError("operations must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("operations must be unique")
        return tuple(sorted(values, key=lambda item: item.value))

    @field_validator("rate_limit")
    @classmethod
    def normalize_rate_limits(
        cls,
        values: tuple[RateLimitPolicy, ...],
    ) -> tuple[RateLimitPolicy, ...]:
        operations = [value.operation for value in values]
        if len(operations) != len(set(operations)):
            raise ValueError("rate_limit must contain at most one policy per operation")
        return tuple(sorted(values, key=lambda item: item.operation.value))

    @model_validator(mode="after")
    def validate_capability_consistency(self) -> Self:
        operation_set = set(self.operations)
        supported_markets = set(self.supported_markets)
        scoped_operation_set = {
            item.operation for item in self.market_data_capabilities
        }
        declared_market_data_operations = operation_set & _MARKET_DATA_OPERATIONS
        if scoped_operation_set != declared_market_data_operations:
            raise ValueError(
                "market_data_capabilities must cover every declared "
                "market-data operation"
            )
        if any(
            item.market not in supported_markets
            for item in self.market_data_capabilities
        ):
            raise ValueError(
                "market_data_capabilities reference an unsupported market"
            )
        if any(policy.operation not in operation_set for policy in self.rate_limit):
            raise ValueError("rate_limit references an undeclared operation")

        feature_operations = (
            (
                self.supports_options,
                {ProviderOperation.OPTION_CHAIN, ProviderOperation.OPTION_SNAPSHOT},
                "options",
            ),
            (
                self.supports_fundamentals,
                {
                    ProviderOperation.FUNDAMENTALS,
                    ProviderOperation.ESTIMATES,
                    ProviderOperation.CORPORATE_ACTIONS,
                },
                "fundamentals",
            ),
            (self.supports_news, {ProviderOperation.NEWS}, "news"),
            (self.supports_filings, {ProviderOperation.FILINGS}, "filings"),
            (self.supports_streaming, {ProviderOperation.STREAM_QUOTES}, "streaming"),
        )
        for enabled, related_operations, label in feature_operations:
            has_operation = bool(operation_set & related_operations)
            if enabled != has_operation:
                raise ValueError(f"supports_{label} disagrees with declared operations")
        return self


class MarketDataAccess(ProviderContract):
    """Observed quality and session entitlement for one market operation."""

    market: Market
    operation: ProviderOperation
    data_quality: DataDeliveryQuality
    allows_premarket: bool = False
    allows_afterhours: bool = False

    @model_validator(mode="after")
    def validate_session_entitlement(self) -> Self:
        if self.operation not in _MARKET_DATA_OPERATIONS:
            raise ValueError("market data access requires a market-data operation")
        if self.data_quality is DataDeliveryQuality.UNAVAILABLE and (
            self.allows_premarket or self.allows_afterhours
        ):
            raise ValueError("unavailable market data cannot allow extended-hours sessions")
        return self


class ProviderAccessProfile(ProviderContract):
    """Verified account entitlement kept separate from technical capability."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    provider_name: NonEmptyText
    provider_version: NonEmptyText
    status: ProviderAccessStatus
    access_scope: NonEmptyText
    verified_at: datetime | None = None
    enabled_operations: tuple[ProviderOperation, ...] = ()
    market_data_quality: tuple[MarketDataAccess, ...] = ()
    notes: tuple[NonEmptyText, ...] = ()

    @field_validator("verified_at")
    @classmethod
    def normalize_verified_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value)

    @field_validator("enabled_operations")
    @classmethod
    def normalize_enabled_operations(
        cls,
        values: tuple[ProviderOperation, ...],
    ) -> tuple[ProviderOperation, ...]:
        if len(values) != len(set(values)):
            raise ValueError("enabled_operations must be unique")
        return tuple(sorted(values, key=lambda item: item.value))

    @field_validator("market_data_quality")
    @classmethod
    def normalize_market_data_quality(
        cls,
        values: tuple[MarketDataAccess, ...],
    ) -> tuple[MarketDataAccess, ...]:
        keys = [(value.market, value.operation) for value in values]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "market_data_quality must contain at most one entry "
                "per market and operation"
            )
        return tuple(
            sorted(
                values,
                key=lambda item: (item.market.value, item.operation.value),
            )
        )

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("notes must be unique")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def validate_access_state(self) -> Self:
        has_available_market = any(
            item.data_quality is not DataDeliveryQuality.UNAVAILABLE
            for item in self.market_data_quality
        )
        if self.status is ProviderAccessStatus.ENABLED:
            if self.verified_at is None:
                raise ValueError("enabled access must have verified_at")
            if not self.enabled_operations:
                raise ValueError("enabled access must declare enabled_operations")
            if any(
                item.data_quality is not DataDeliveryQuality.UNAVAILABLE
                and item.operation not in self.enabled_operations
                for item in self.market_data_quality
            ):
                raise ValueError(
                    "available market data requires its operation to be enabled"
                )
        elif self.enabled_operations or has_available_market:
            raise ValueError("disabled or unverified access cannot enable operations or data")
        if self.status is ProviderAccessStatus.UNVERIFIED and self.verified_at is not None:
            raise ValueError("unverified access cannot have verified_at")
        return self


class ProviderBarRequest(ProviderContract):
    """Point-in-Time bar request using internal and provider-specific identifiers."""

    instrument_id: UUID
    provider_instrument_id: NonEmptyText
    market: Market
    interval: DataInterval
    start: datetime
    end: datetime
    decision_time: datetime
    include_premarket: bool = False
    include_afterhours: bool = False

    @field_validator("start", "end", "decision_time")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")
        if self.end > self.decision_time:
            raise ValueError("end must not be after decision_time")
        return self

    @property
    def fact_type(self) -> str:
        """Return the canonical fact type expected from this request."""

        return "daily_bar" if self.interval is DataInterval.DAY_1 else "minute_bar"


def validate_provider_access(
    capability: ProviderCapability,
    access: ProviderAccessProfile,
) -> ProviderAccessProfile:
    """Reject account permissions or quality claims unsupported by the adapter."""

    if (
        access.provider_name != capability.provider_name
        or access.provider_version != capability.provider_version
    ):
        raise ValueError("access profile does not match provider capability identity")

    capability_operations = set(capability.operations)
    if any(operation not in capability_operations for operation in access.enabled_operations):
        raise ValueError("access profile enables an unsupported operation")

    supported_markets = set(capability.supported_markets)
    if any(item.market not in supported_markets for item in access.market_data_quality):
        raise ValueError("access profile declares an unsupported market")

    scoped_capabilities = {
        (item.market, item.operation): item
        for item in capability.market_data_capabilities
    }
    for item in access.market_data_quality:
        scoped_capability = scoped_capabilities.get((item.market, item.operation))
        if scoped_capability is None:
            raise ValueError(
                "access profile declares an unsupported market-data operation"
            )
        if (
            item.data_quality is DataDeliveryQuality.REALTIME
            and not scoped_capability.supports_realtime
        ):
            raise ValueError(
                "access profile claims realtime data the adapter does not support "
                "for this market and operation"
            )
        if item.allows_premarket and not scoped_capability.supports_premarket:
            raise ValueError(
                "access profile claims premarket data the adapter does not support "
                "for this market and operation"
            )
        if item.allows_afterhours and not scoped_capability.supports_afterhours:
            raise ValueError(
                "access profile claims after-hours data the adapter does not support "
                "for this market and operation"
            )
    return access


def validate_bar_request(
    capability: ProviderCapability,
    access: ProviderAccessProfile,
    request: ProviderBarRequest,
) -> ProviderBarRequest:
    """Validate one bar request against both technical and account-level boundaries."""

    validate_provider_access(capability, access)
    if ProviderOperation.BARS not in capability.operations:
        raise ValueError("provider does not implement bars")
    if ProviderOperation.BARS not in access.enabled_operations:
        raise PermissionError("current provider access does not enable bars")
    if request.market not in capability.supported_markets:
        raise ValueError("provider does not support the requested market")

    key = (request.market, ProviderOperation.BARS)
    scoped_capability = {
        (item.market, item.operation): item
        for item in capability.market_data_capabilities
    }.get(key)
    if scoped_capability is None:
        raise ValueError("provider does not support bars for the requested market")

    market_access = {
        (item.market, item.operation): item
        for item in access.market_data_quality
    }.get(key)
    if (
        market_access is None
        or market_access.data_quality is DataDeliveryQuality.UNAVAILABLE
    ):
        raise PermissionError(
            "current provider access has no bars for the requested market"
        )
    if request.interval not in scoped_capability.supported_intervals:
        raise ValueError("provider does not support the requested interval")

    history_by_interval = {
        window.interval: window.historical_start
        for window in scoped_capability.bar_history
    }
    historical_start = history_by_interval.get(request.interval)
    if historical_start is not None:
        market_timezone = ZoneInfo(MARKET_TIMEZONES[request.market])
        request_start_date = request.start.astimezone(market_timezone).date()
        if request_start_date < historical_start:
            raise ValueError("request starts before provider historical_start")

    if request.include_premarket:
        if not scoped_capability.supports_premarket:
            raise ValueError("provider does not support premarket bars")
        if not market_access.allows_premarket:
            raise PermissionError("current provider access does not allow premarket bars")
    if request.include_afterhours:
        if not scoped_capability.supports_afterhours:
            raise ValueError("provider does not support after-hours bars")
        if not market_access.allows_afterhours:
            raise PermissionError("current provider access does not allow after-hours bars")
    return request
