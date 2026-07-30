"""Vendor-neutral provider capability and entitlement contract tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from pytest import mark, raises

from qfusion.domain import Market
from qfusion.providers import (
    AssetType,
    DataDeliveryQuality,
    DataInterval,
    MarketDataAccess,
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
        "supported_intervals": (DataInterval.DAY_1,),
        "supports_realtime": False,
        "supports_premarket": False,
        "supports_afterhours": False,
        "supports_options": False,
        "supports_fundamentals": False,
        "supports_news": False,
        "supports_filings": False,
        "supports_streaming": False,
        "rate_limit": (),
        "historical_start": date(2020, 1, 1),
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
        "include_extended_hours": False,
    }
    data.update(overrides)
    return ProviderBarRequest.model_validate(data)


def test_capability_canonicalizes_collections_and_rate_limits() -> None:
    capability = make_capability(
        supported_markets=(Market.US, Market.HK),
        supported_asset_types=(AssetType.STOCK, AssetType.ADR),
        supported_intervals=(DataInterval.MINUTE_1, DataInterval.DAY_1),
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
    assert capability.supported_intervals == (DataInterval.MINUTE_1, DataInterval.DAY_1)
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
        (
            "supported_intervals",
            (DataInterval.DAY_1, DataInterval.DAY_1),
            "supported_intervals must be unique",
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


def test_capability_rejects_bars_without_intervals_and_orphan_extended_hours() -> None:
    with raises(ValidationError, match="bars capability requires"):
        make_capability(supported_intervals=())

    with raises(ValidationError, match="extended-hours"):
        make_capability(
            operations=(ProviderOperation.FILINGS,),
            supported_intervals=(),
            supports_filings=True,
            supports_premarket=True,
        )

    with raises(ValidationError, match="realtime"):
        make_capability(
            operations=(ProviderOperation.FILINGS,),
            supported_intervals=(),
            supports_filings=True,
            supports_realtime=True,
        )


def test_capability_accepts_coherent_feature_and_realtime_declarations() -> None:
    capability = make_capability(
        supports_realtime=True,
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

    assert capability.supports_realtime
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

    with raises(ValidationError, match=f"supports_{label}"):
        make_capability(operations=(ProviderOperation.BARS, operation))


def test_access_profile_normalizes_timestamp_collections_and_notes() -> None:
    offset = timezone(timedelta(hours=8))
    access = make_access(
        verified_at=datetime(2026, 7, 31, 4, 0, tzinfo=offset),
        enabled_operations=(ProviderOperation.QUOTES, ProviderOperation.BARS),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                data_quality=DataDeliveryQuality.DELAYED,
            ),
            MarketDataAccess(
                market=Market.HK,
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
                    data_quality=DataDeliveryQuality.HISTORICAL,
                ),
                MarketDataAccess(
                    market=Market.US,
                    data_quality=DataDeliveryQuality.DELAYED,
                ),
            ),
            "at most one entry per market",
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
            make_access(enabled_operations=(ProviderOperation.QUOTES,)),
        )
    with raises(ValueError, match="unsupported market"):
        validate_provider_access(
            capability,
            make_access(
                market_data_quality=(
                    MarketDataAccess(
                        market=Market.HK,
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


def test_provider_access_allows_realtime_only_when_capability_supports_it() -> None:
    capability = make_capability(supports_realtime=True)
    access = make_access(
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                data_quality=DataDeliveryQuality.REALTIME,
            ),
        ),
    )

    assert validate_provider_access(capability, access) is access


def test_unavailable_market_entry_does_not_claim_market_data() -> None:
    capability = make_capability(
        operations=(ProviderOperation.NEWS,),
        supported_intervals=(),
        supports_news=True,
    )
    access = make_access(
        enabled_operations=(ProviderOperation.NEWS,),
        market_data_quality=(
            MarketDataAccess(
                market=Market.US,
                data_quality=DataDeliveryQuality.UNAVAILABLE,
            ),
        ),
    )

    assert validate_provider_access(capability, access) is access


def test_provider_access_requires_market_data_operation_for_quality_claim() -> None:
    capability = make_capability(
        operations=(ProviderOperation.NEWS,),
        supported_intervals=(),
        supports_news=True,
    )
    access = make_access(enabled_operations=(ProviderOperation.NEWS,))

    with raises(ValueError, match="market-data operation"):
        validate_provider_access(capability, access)


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
        supported_intervals=(),
        supports_news=True,
    )
    no_bars_access = make_access(
        enabled_operations=(ProviderOperation.NEWS,),
        market_data_quality=(),
    )
    with raises(ValueError, match="does not implement bars"):
        validate_bar_request(no_bars, no_bars_access, request)

    quotes_capability = make_capability(\n        operations=(ProviderOperation.BARS, ProviderOperation.QUOTES)\n    )
    quotes_access = make_access(enabled_operations=(ProviderOperation.QUOTES,))
    with raises(PermissionError, match="does not enable bars"):
        validate_bar_request(quotes_capability, quotes_access, request)

    with raises(PermissionError, match="no data"):
        validate_bar_request(capability, make_access(market_data_quality=()), request)


def test_bar_request_rejects_unsupported_market_interval_and_extended_hours() -> None:
    capability = make_capability()
    access = make_access()

    hk_request = make_request(market=Market.HK)
    with raises(ValueError, match="requested market"):
        validate_bar_request(capability, access, hk_request)

    minute_request = make_request(interval=DataInterval.MINUTE_1)
    with raises(ValueError, match="requested interval"):
        validate_bar_request(capability, access, minute_request)

    extended_request = make_request(include_extended_hours=True)
    with raises(ValueError, match="extended-hours"):
        validate_bar_request(capability, access, extended_request)

    extended_capability = make_capability(supports_premarket=True)
    assert (
        validate_bar_request(extended_capability, access, extended_request)
        is extended_request
    )
