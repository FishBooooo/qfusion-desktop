"""Vendor-neutral provider capability and entitlement contract tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from pytest import mark, raises

from qfusion.domain import Market
from qfusion.providers import (
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
    RateLimitPolicy,
    validate_bar_request,
    validate_provider_access,
)

INSTRUMENT_ID = UUID("10000000-0000-4000-8000-000000000001")
DECISION_TIME = datetime(2026, 7, 30, 20, 0, tzinfo=UTC)


def make_capability(**overrides: object) -> ProviderCapability:
    data: dict[str, object] = {
        "provider_name": "test-provider",
        "provider_version": "1.0.0",
        "supported_markets": (Market.US,),
        "supported_asset_types": (AssetType.STOCK,),
        "market_data_capabilities": (
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2020, 1, 1),
                    ),
                ),
            ),
        ),
        "supports_options": False,
        "supports_fundamentals": False,
        "supports_news": False,
        "supports_filings": False,
        "supports_streaming": False,
        "rate_limit": (),
        "venue_scope": "US",
        "quality_level": "test",
        "license_scope": "test-only",
        "operations": (ProviderOperation.BARS,),
    }
    data.update(overrides)
    return ProviderCapability.model_validate(data)


def make_access(**overrides: object) -> ProviderAccessProfile:
    data: dict[str, object] = {
        "provider_name": "test-provider",
        "provider_version": "1.0.0",
        "status": ProviderAccessStatus.ENABLED,
        "access_scope": "unit-test",
        "verified_at": DECISION_TIME,
        "enabled_operations": (ProviderOperation.BARS,),
        "market_data_quality": (
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
            ),
        ),
        "notes": (),
    }
    data.update(overrides)
    return ProviderAccessProfile.model_validate(data)


def make_request(**overrides: object) -> ProviderBarRequest:
    data: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "provider_instrument_id": "opaque-provider-id-1",
        "market": Market.US,
        "interval": DataInterval.DAY_1,
        "start": DECISION_TIME - timedelta(days=5),
        "end": DECISION_TIME,
        "decision_time": DECISION_TIME,
        "include_premarket": False,
        "include_afterhours": False,
    }
    data.update(overrides)
    return ProviderBarRequest.model_validate(data)


def test_capability_canonicalizes_collections_and_rate_limits() -> None:
    capability = make_capability(
        supported_markets=(Market.US, Market.HK),
        supported_asset_types=(AssetType.STOCK, AssetType.ADR),
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
            ),
            MarketDataCapability(
                market=Market.HK,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.MINUTE_1, DataInterval.DAY_1),
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2010, 1, 1),
                    ),
                ),
            ),
        ),
        operations=(ProviderOperation.QUOTES, ProviderOperation.BARS),
        rate_limit=(
            RateLimitPolicy(
                operation=ProviderOperation.QUOTES,
                max_requests=10,
                window_seconds=1,
                max_concurrent=2,
            ),
            RateLimitPolicy(
                operation=ProviderOperation.BARS,
                max_requests=60,
                window_seconds=60,
            ),
        ),
    )

    assert capability.supported_markets == (Market.HK, Market.US)
    assert capability.supported_asset_types == (AssetType.ADR, AssetType.STOCK)
    assert tuple(
        (item.market, item.operation)
        for item in capability.market_data_capabilities
    ) == (
        (Market.HK, ProviderOperation.BARS),
        (Market.US, ProviderOperation.QUOTES),
    )
    assert capability.market_data_capabilities[0].supported_intervals == (
        DataInterval.MINUTE_1,
        DataInterval.DAY_1,
    )
    assert capability.operations == (ProviderOperation.BARS, ProviderOperation.QUOTES)
    assert tuple(item.operation for item in capability.rate_limit) == (
        ProviderOperation.BARS,
        ProviderOperation.QUOTES,
    )


@mark.parametrize(
    ("field", "value", "message"),
    [
        ("supported_markets", (), "supported_markets must not be empty"),
        ("supported_markets", (Market.US, Market.US), "supported_markets must be unique"),
        ("supported_asset_types", (), "supported_asset_types must not be empty"),
        (
            "supported_asset_types",
            (AssetType.STOCK, AssetType.STOCK),
            "supported_asset_types must be unique",
        ),
        ("operations", (), "operations must not be empty"),
        (
            "operations",
            (ProviderOperation.BARS, ProviderOperation.BARS),
            "operations must be unique",
        ),
    ],
)
def test_capability_rejects_empty_or_duplicate_collections(
    field: str,
    value: object,
    message: str,
) -> None:
    with raises(ValidationError, match=message):
        make_capability(**{field: value})


def test_capability_rejects_duplicate_or_orphan_rate_limits() -> None:
    policy = RateLimitPolicy(
        operation=ProviderOperation.BARS,
        max_requests=1,
        window_seconds=1,
    )
    with raises(ValidationError, match="at most one policy"):
        make_capability(rate_limit=(policy, policy))

    orphan = RateLimitPolicy(
        operation=ProviderOperation.QUOTES,
        max_requests=1,
        window_seconds=1,
    )
    with raises(ValidationError, match="undeclared operation"):
        make_capability(rate_limit=(orphan,))


def test_scoped_market_data_capability_rejects_invalid_combinations() -> None:
    with raises(ValidationError, match="bars capability requires"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.BARS,
        )

    with raises(ValidationError, match="only bars"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.QUOTES,
            supported_intervals=(DataInterval.DAY_1,),
        )

    with raises(ValidationError, match="market-data operation"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.FILINGS,
        )

    with raises(ValidationError, match="supported_intervals must be unique"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.BARS,
            supported_intervals=(DataInterval.DAY_1, DataInterval.DAY_1),
        )

    history = BarHistoryWindow(
        interval=DataInterval.DAY_1,
        historical_start=date(2020, 1, 1),
    )
    with raises(ValidationError, match="at most one start per interval"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.BARS,
            supported_intervals=(DataInterval.DAY_1,),
            bar_history=(history, history),
        )

    with raises(ValidationError, match="unsupported interval"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.BARS,
            supported_intervals=(DataInterval.DAY_1,),
            bar_history=(
                BarHistoryWindow(
                    interval=DataInterval.MINUTE_1,
                    historical_start=date(2020, 1, 1),
                ),
            ),
        )

    with raises(ValidationError, match="only bars"):
        MarketDataCapability(
            market=Market.US,
            operation=ProviderOperation.QUOTES,
            bar_history=(history,),
        )


def test_capability_rejects_duplicate_missing_or_unsupported_scoped_entries() -> None:
    bars = MarketDataCapability(
        market=Market.US,
        operation=ProviderOperation.BARS,
        supported_intervals=(DataInterval.DAY_1,),
    )
    with raises(ValidationError, match="at most one entry"):
        make_capability(market_data_capabilities=(bars, bars))

    with raises(ValidationError, match="cover every declared"):
        make_capability(market_data_capabilities=())

    with raises(ValidationError, match="unsupported market"):
        make_capability(
            market_data_capabilities=(
                MarketDataCapability(
                    market=Market.HK,
                    operation=ProviderOperation.BARS,
                    supported_intervals=(DataInterval.DAY_1,),
                ),
            ),
        )


def test_capability_accepts_coherent_feature_and_realtime_declarations() -> None:
    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
            ),
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.STREAM_QUOTES,
                supports_realtime=True,
            ),
        ),
        supports_options=True,
        supports_fundamentals=True,
        supports_news=True,
        supports_filings=True,
        supports_streaming=True,
        operations=(
            ProviderOperation.BARS,
            ProviderOperation.CORPORATE_ACTIONS,
            ProviderOperation.ESTIMATES,
            ProviderOperation.FILINGS,
            ProviderOperation.FUNDAMENTALS,
            ProviderOperation.NEWS,
            ProviderOperation.OPTION_CHAIN,
            ProviderOperation.OPTION_SNAPSHOT,
            ProviderOperation.STREAM_QUOTES,
        ),
    )

    assert any(
        item.supports_realtime
        for item in capability.market_data_capabilities
    )
    assert capability.supports_options
    assert capability.supports_fundamentals
    assert capability.supports_news
    assert capability.supports_filings
    assert capability.supports_streaming


@mark.parametrize(
    ("flag", "operation", "label"),
    [
        ("supports_options", ProviderOperation.OPTION_CHAIN, "options"),
        ("supports_fundamentals", ProviderOperation.FUNDAMENTALS, "fundamentals"),
        ("supports_news", ProviderOperation.NEWS, "news"),
        ("supports_filings", ProviderOperation.FILINGS, "filings"),
        ("supports_streaming", ProviderOperation.STREAM_QUOTES, "streaming"),
    ],
)
def test_capability_feature_flags_must_match_operations(
    flag: str,
    operation: ProviderOperation,
    label: str,
) -> None:
    with raises(ValidationError, match=f"supports_{label}"):
        make_capability(**{flag: True})

    operation_overrides: dict[str, object] = {
        "operations": (ProviderOperation.BARS, operation),
    }
    if operation is ProviderOperation.STREAM_QUOTES:
        operation_overrides["market_data_capabilities"] = (
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
            ),
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.STREAM_QUOTES,
            ),
        )
    with raises(ValidationError, match=f"supports_{label}"):
        make_capability(**operation_overrides)


def test_access_profile_normalizes_timestamp_collections_and_notes() -> None:
    offset = timezone(timedelta(hours=8))
    access = make_access(
        verified_at=datetime(2026, 7, 31, 4, 0, tzinfo=offset),
        enabled_operations=(ProviderOperation.QUOTES, ProviderOperation.BARS),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.DELAYED,
            ),
            MarketDataAccess(
                market=Market.HK,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
            ),
        ),
        notes=("z-note", "a-note"),
    )

    assert access.verified_at == DECISION_TIME
    assert access.enabled_operations == (ProviderOperation.BARS, ProviderOperation.QUOTES)
    assert tuple(item.market for item in access.market_data_quality) == (Market.HK, Market.US)
    assert access.notes == ("a-note", "z-note")


@mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "enabled_operations",
            (ProviderOperation.BARS, ProviderOperation.BARS),
            "enabled_operations must be unique",
        ),
        (
            "market_data_quality",
            (
                MarketDataAccess(
                    market=Market.US,
                    operation=ProviderOperation.BARS,
                    data_quality=DataDeliveryQuality.HISTORICAL,
                ),
                MarketDataAccess(
                    market=Market.US,
                    operation=ProviderOperation.BARS,
                    data_quality=DataDeliveryQuality.DELAYED,
                ),
            ),
            "per market and operation",
        ),
        ("notes", ("same", "same"), "notes must be unique"),
    ],
)
def test_access_profile_rejects_duplicate_collections(
    field: str,
    value: object,
    message: str,
) -> None:
    with raises(ValidationError, match=message):
        make_access(**{field: value})


def test_access_profile_rejects_invalid_state_combinations() -> None:
    with raises(ValidationError, match="verified_at"):
        make_access(verified_at=None)
    with raises(ValidationError, match="enabled_operations"):
        make_access(enabled_operations=())
    with raises(ValidationError, match="cannot enable"):
        make_access(status=ProviderAccessStatus.DISABLED)
    with raises(ValidationError, match="cannot enable"):
        make_access(
            status=ProviderAccessStatus.DISABLED,
            enabled_operations=(),
            market_data_quality=(
                MarketDataAccess(
                    market=Market.US,
                    operation=ProviderOperation.BARS,
                    data_quality=DataDeliveryQuality.HISTORICAL,
                ),
            ),
        )
    with raises(ValidationError, match="unverified access cannot have verified_at"):
        make_access(
            status=ProviderAccessStatus.UNVERIFIED,
            enabled_operations=(),
            market_data_quality=(),
        )


def test_access_profile_rejects_naive_verified_at() -> None:
    with raises(ValidationError, match="timezone-aware"):
        make_access(verified_at=datetime(2026, 7, 30, 20, 0))


def test_provider_access_validates_identity_operations_markets_and_quality() -> None:
    capability = make_capability()
    access = make_access()
    assert validate_provider_access(capability, access) is access

    with raises(ValueError, match="identity"):
        validate_provider_access(capability, make_access(provider_name="other"))
    with raises(ValueError, match="unsupported operation"):
        validate_provider_access(
            capability,
            make_access(
                enabled_operations=(ProviderOperation.QUOTES,),
                market_data_quality=(),
            ),
        )
    with raises(ValueError, match="unsupported market"):
        validate_provider_access(
            capability,
            make_access(
                market_data_quality=(
                    MarketDataAccess(
                        market=Market.HK,
                        operation=ProviderOperation.BARS,
                        data_quality=DataDeliveryQuality.HISTORICAL,
                    ),
                ),
            ),
        )
    with raises(ValueError, match="realtime"):
        validate_provider_access(
            capability,
            make_access(
                market_data_quality=(
                    MarketDataAccess(
                        market=Market.US,
                        operation=ProviderOperation.BARS,
                        data_quality=DataDeliveryQuality.REALTIME,
                    ),
                ),
            ),
        )
    with raises(ValueError, match="identity"):
        validate_provider_access(
            capability,
            make_access(provider_version="2.0.0"),
        )


def test_provider_access_rejects_unsupported_scoped_market_operation() -> None:
    access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
                data_quality=DataDeliveryQuality.UNAVAILABLE,
            ),
        ),
    )

    with raises(ValueError, match="unsupported market-data operation"):
        validate_provider_access(make_capability(), access)


def test_provider_access_allows_realtime_only_when_capability_supports_it() -> None:
    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_realtime=True,
            ),
        ),
    )
    access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.REALTIME,
            ),
        ),
    )

    assert validate_provider_access(capability, access) is access


def test_unavailable_market_entry_does_not_claim_market_data() -> None:
    capability = make_capability(
        operations=(ProviderOperation.BARS, ProviderOperation.NEWS),
        supports_news=True,
    )
    access = make_access(
        enabled_operations=(ProviderOperation.NEWS,),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.UNAVAILABLE,
            ),
        ),
    )

    assert validate_provider_access(capability, access) is access


@mark.parametrize("field", ("allows_premarket", "allows_afterhours"))
def test_unavailable_market_rejects_extended_hours_entitlement(field: str) -> None:
    with raises(ValidationError, match="unavailable market data"):
        MarketDataAccess.model_validate(
            {
                "market": Market.US,
                "operation": ProviderOperation.BARS,
                "data_quality": DataDeliveryQuality.UNAVAILABLE,
                field: True,
            }
        )


def test_provider_access_rejects_unsupported_extended_hours_claims() -> None:
    premarket_access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
                allows_premarket=True,
            ),
        ),
    )
    with raises(ValueError, match="premarket"):
        validate_provider_access(make_capability(), premarket_access)

    afterhours_access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
                allows_afterhours=True,
            ),
        ),
    )
    with raises(ValueError, match="after-hours"):
        validate_provider_access(make_capability(), afterhours_access)


def test_access_profile_requires_available_operation_to_be_enabled() -> None:
    with raises(ValidationError, match="operation to be enabled"):
        make_access(enabled_operations=(ProviderOperation.NEWS,))


def test_bar_request_normalizes_times_and_derives_fact_type() -> None:
    offset = timezone(timedelta(hours=-4))
    request = make_request(
        start=datetime(2026, 7, 30, 15, 0, tzinfo=offset),
        end=datetime(2026, 7, 30, 16, 0, tzinfo=offset),
        interval=DataInterval.MINUTE_1,
    )

    assert request.start == datetime(2026, 7, 30, 19, 0, tzinfo=UTC)
    assert request.end == DECISION_TIME
    assert request.fact_type == "minute_bar"
    assert make_request().fact_type == "daily_bar"


def test_bar_request_rejects_naive_or_invalid_time_ranges() -> None:
    with raises(ValidationError, match="timezone-aware"):
        make_request(start=datetime(2026, 7, 25, 20, 0))
    with raises(ValidationError, match="start must be earlier"):
        make_request(start=DECISION_TIME, end=DECISION_TIME)
    with raises(ValidationError, match="end must not be after"):
        make_request(
            end=DECISION_TIME + timedelta(seconds=1),
            decision_time=DECISION_TIME,
        )


def test_bar_request_checks_capability_entitlement_and_market_quality() -> None:
    capability = make_capability()
    access = make_access()
    request = make_request()
    assert validate_bar_request(capability, access, request) is request

    no_bars = make_capability(
        operations=(ProviderOperation.NEWS,),
        market_data_capabilities=(),
        supports_news=True,
    )
    no_bars_access = make_access(
        enabled_operations=(ProviderOperation.NEWS,),
        market_data_quality=(),
    )
    with raises(ValueError, match="does not implement bars"):
        validate_bar_request(no_bars, no_bars_access, request)

    quotes_capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2020, 1, 1),
                    ),
                ),
            ),
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
            ),
        ),
        operations=(ProviderOperation.BARS, ProviderOperation.QUOTES),
    )
    quotes_access = make_access(
        enabled_operations=(ProviderOperation.QUOTES,),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
                data_quality=DataDeliveryQuality.HISTORICAL,
            ),
        ),
    )
    with raises(PermissionError, match="does not enable bars"):
        validate_bar_request(quotes_capability, quotes_access, request)

    with raises(PermissionError, match="no bars for the requested market"):
        validate_bar_request(capability, make_access(market_data_quality=()), request)


def test_bar_request_rejects_unsupported_market_and_interval() -> None:
    capability = make_capability()
    access = make_access()

    hk_request = make_request(market=Market.HK)
    with raises(ValueError, match="requested market"):
        validate_bar_request(capability, access, hk_request)

    minute_request = make_request(interval=DataInterval.MINUTE_1)
    with raises(ValueError, match="requested interval"):
        validate_bar_request(capability, access, minute_request)


def test_bar_request_checks_premarket_capability_and_account_access() -> None:
    request = make_request(include_premarket=True)
    access = make_access()

    with raises(ValueError, match="premarket"):
        validate_bar_request(make_capability(), access, request)

    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_premarket=True,
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2020, 1, 1),
                    ),
                ),
            ),
        ),
    )
    with raises(PermissionError, match="premarket"):
        validate_bar_request(capability, access, request)

    entitled_access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
                allows_premarket=True,
            ),
        ),
    )
    assert validate_bar_request(capability, entitled_access, request) is request


def test_bar_request_checks_afterhours_capability_and_account_access() -> None:
    request = make_request(include_afterhours=True)
    access = make_access()

    with raises(ValueError, match="after-hours"):
        validate_bar_request(make_capability(), access, request)

    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_afterhours=True,
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2020, 1, 1),
                    ),
                ),
            ),
        ),
    )
    with raises(PermissionError, match="after-hours"):
        validate_bar_request(capability, access, request)

    entitled_access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
                allows_afterhours=True,
            ),
        ),
    )
    assert validate_bar_request(capability, entitled_access, request) is request


def test_bar_request_enforces_historical_start_in_market_timezone() -> None:
    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2020, 1, 1),
                    ),
                ),
            ),
        ),
    )
    access = make_access()
    before_us_boundary = make_request(
        start=datetime(2020, 1, 1, 1, 0, tzinfo=UTC),
    )

    with raises(ValueError, match="historical_start"):
        validate_bar_request(capability, access, before_us_boundary)

    at_us_boundary = make_request(
        start=datetime(2020, 1, 1, 5, 0, tzinfo=UTC),
    )
    assert validate_bar_request(capability, access, at_us_boundary) is at_us_boundary


def test_bar_request_scopes_historical_start_by_interval() -> None:
    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.MINUTE_1, DataInterval.DAY_1),
                bar_history=(
                    BarHistoryWindow(
                        interval=DataInterval.DAY_1,
                        historical_start=date(2000, 1, 1),
                    ),
                    BarHistoryWindow(
                        interval=DataInterval.MINUTE_1,
                        historical_start=date(2025, 1, 1),
                    ),
                ),
            ),
        ),
    )
    access = make_access()
    old_start = datetime(2020, 1, 2, 5, 0, tzinfo=UTC)

    daily_request = make_request(start=old_start)
    assert validate_bar_request(capability, access, daily_request) is daily_request

    minute_request = make_request(
        interval=DataInterval.MINUTE_1,
        start=old_start,
    )
    with raises(ValueError, match="historical_start"):
        validate_bar_request(capability, access, minute_request)


def test_bar_request_rejects_cross_market_extended_hours_capability() -> None:
    capability = make_capability(
        supported_markets=(Market.US, Market.HK),
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_premarket=True,
            ),
            MarketDataCapability(
                market=Market.HK,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
            ),
        ),
    )
    access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.HK,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
            ),
        ),
    )
    request = make_request(market=Market.HK, include_premarket=True)

    with raises(ValueError, match="premarket"):
        validate_bar_request(capability, access, request)


def test_bar_request_rejects_cross_operation_extended_hours_capability() -> None:
    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
            ),
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
                supports_premarket=True,
            ),
        ),
        operations=(ProviderOperation.BARS, ProviderOperation.QUOTES),
    )
    access = make_access()
    request = make_request(include_premarket=True)

    with raises(ValueError, match="premarket"):
        validate_bar_request(capability, access, request)


def test_bar_request_rejects_cross_market_account_entitlement() -> None:
    capability = make_capability(
        supported_markets=(Market.US, Market.HK),
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_premarket=True,
            ),
            MarketDataCapability(
                market=Market.HK,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_premarket=True,
            ),
        ),
    )
    access = make_access(
        enabled_operations=(ProviderOperation.BARS,),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
                allows_premarket=True,
            ),
            MarketDataAccess(
                market=Market.HK,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
            ),
        ),
    )
    request = make_request(market=Market.HK, include_premarket=True)

    with raises(PermissionError, match="premarket"):
        validate_bar_request(capability, access, request)


def test_bar_request_rejects_cross_operation_account_entitlement() -> None:
    capability = make_capability(
        market_data_capabilities=(
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.BARS,
                supported_intervals=(DataInterval.DAY_1,),
                supports_afterhours=True,
            ),
            MarketDataCapability(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
                supports_afterhours=True,
            ),
        ),
        operations=(ProviderOperation.BARS, ProviderOperation.QUOTES),
    )
    access = make_access(
        enabled_operations=(ProviderOperation.BARS, ProviderOperation.QUOTES),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.BARS,
                data_quality=DataDeliveryQuality.HISTORICAL,
            ),
            MarketDataAccess(
                market=Market.US,
                operation=ProviderOperation.QUOTES,
                data_quality=DataDeliveryQuality.HISTORICAL,
                allows_afterhours=True,
            ),
        ),
    )
    request = make_request(include_afterhours=True)

    with raises(PermissionError, match="after-hours"):
        validate_bar_request(capability, access, request)
