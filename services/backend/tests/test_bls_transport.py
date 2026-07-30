"""Mock-transport tests for BLS DNS, redirects, retry, and local budgets."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

import httpx
from pytest import raises

from qfusion.providers.bls import (
    BlsHttpTransport,
    BlsNetworkPolicyError,
    BlsPayloadError,
    BlsRateLimitError,
    BlsSeriesRequest,
    BlsTransportConfig,
    BlsTransportError,
    require_bls_public_addresses,
)

_NOW: Final = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
_REQUEST: Final = BlsSeriesRequest(
    series_ids=("QFUSION_TEST_01",),
    start_year=2025,
    end_year=2026,
)


class StaticResolver:
    def __init__(self, addresses: tuple[str, ...]) -> None:
        self.addresses = addresses
        self.hosts: list[str] = []

    async def resolve(self, host: str) -> tuple[str, ...]:
        self.hosts.append(host)
        return self.addresses


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.delays: list[float] = []

    def monotonic(self) -> float:
        return self.value

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        self.value += delay


def config(**overrides: object) -> BlsTransportConfig:
    values: dict[str, object] = {"user_agent": "QFusion CI ci@example.com"}
    values.update(overrides)
    return BlsTransportConfig.model_validate(values)


async def fetch_and_close(transport: BlsHttpTransport):
    try:
        return await transport.get_series(_REQUEST)
    finally:
        await transport.aclose()


def make_transport(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    resolver: StaticResolver | None = None,
    clock: FakeClock | None = None,
    transport_config: BlsTransportConfig | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> BlsHttpTransport:
    selected_clock = clock or FakeClock()
    return BlsHttpTransport(
        transport_config or config(),
        resolver=resolver or StaticResolver(("93.184.216.34",)),
        http_transport=httpx.MockTransport(handler),
        sleep=selected_clock.sleep,
        monotonic=selected_clock.monotonic,
        utc_now=utc_now or (lambda: _NOW),
    )


def successful_response() -> dict[str, object]:
    return {
        "status": "REQUEST_SUCCEEDED",
        "message": [],
        "Results": {"series": []},
    }


def test_public_address_policy_rejects_empty_private_local_and_invalid_results() -> None:
    with raises(BlsNetworkPolicyError, match="no addresses"):
        require_bls_public_addresses("api.bls.gov", ())
    for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "invalid"):
        with raises(BlsNetworkPolicyError):
            require_bls_public_addresses("api.bls.gov", (address,))

    require_bls_public_addresses("api.bls.gov", ("93.184.216.34", "2606:4700::6810:1"))


def test_success_uses_fixed_origin_credential_free_body_and_declared_headers() -> None:
    requests: list[httpx.Request] = []
    resolver = StaticResolver(("93.184.216.34",))

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=successful_response(),
            headers={"Content-Type": "application/json"},
        )

    response = asyncio.run(
        fetch_and_close(make_transport(handler, resolver=resolver))
    )

    assert response.received_at == _NOW
    assert response.payload["status"] == "REQUEST_SUCCEEDED"
    assert json.loads(response.raw_body) == response.payload
    assert len(response.raw_body_sha256) == 64
    assert response.content_type == "application/json"
    assert resolver.hosts == ["api.bls.gov"]
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url == httpx.URL(
        "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    )
    assert request.headers["User-Agent"] == "QFusion CI ci@example.com"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Accept-Encoding"] == "identity"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == _REQUEST.api_payload()
    assert b"registrationkey" not in request.content


def test_private_dns_blocks_before_http_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=successful_response())

    with raises(BlsNetworkPolicyError):
        asyncio.run(
            fetch_and_close(
                make_transport(
                    handler,
                    resolver=StaticResolver(("127.0.0.1",)),
                )
            )
        )
    assert calls == 0


def test_redirect_is_never_followed() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/private"},
        )

    with raises(BlsTransportError, match="redirects"):
        asyncio.run(fetch_and_close(make_transport(handler)))
    assert len(requests) == 1


def test_retryable_status_honors_bounded_retry_after_then_succeeds() -> None:
    calls = 0
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "99"})
        return httpx.Response(200, json=successful_response())

    response = asyncio.run(
        fetch_and_close(
            make_transport(
                handler,
                clock=clock,
                transport_config=config(max_retry_delay_seconds=1.5),
            )
        )
    )

    assert response.payload["status"] == "REQUEST_SUCCEEDED"
    assert calls == 2
    assert clock.delays == [1.5, 0.5]
    assert sum(clock.delays) == 2.0


def test_transport_errors_retry_and_invalid_retry_after_is_bounded() -> None:
    timeout_calls = 0
    clock = FakeClock()

    def timeout_then_success(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        if timeout_calls == 1:
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(200, json=successful_response())

    assert asyncio.run(
        fetch_and_close(make_transport(timeout_then_success, clock=clock))
    ).payload["status"] == "REQUEST_SUCCEEDED"
    assert timeout_calls == 2
    assert 0.25 in clock.delays

    status_calls = 0

    def invalid_retry_after(request: httpx.Request) -> httpx.Response:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 1:
            return httpx.Response(503, headers={"Retry-After": "invalid"})
        return httpx.Response(200, json=successful_response())

    retry_clock = FakeClock()
    asyncio.run(fetch_and_close(make_transport(invalid_retry_after, clock=retry_clock)))
    assert 0.0 in retry_clock.delays


def test_nonretryable_and_exhausted_failures_raise_typed_errors() -> None:
    not_found_calls = 0

    def not_found(request: httpx.Request) -> httpx.Response:
        nonlocal not_found_calls
        not_found_calls += 1
        return httpx.Response(404)

    with raises(BlsTransportError, match="HTTP 404"):
        asyncio.run(fetch_and_close(make_transport(not_found)))
    assert not_found_calls == 1

    status_calls = 0

    def unavailable(request: httpx.Request) -> httpx.Response:
        nonlocal status_calls
        status_calls += 1
        return httpx.Response(503)

    with raises(BlsTransportError, match="exhausted retries"):
        asyncio.run(
            fetch_and_close(
                make_transport(
                    unavailable,
                    transport_config=config(max_attempts=2),
                )
            )
        )
    assert status_calls == 2

    timeout_calls = 0

    def always_timeout(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        raise httpx.ConnectTimeout("synthetic timeout", request=request)

    with raises(BlsTransportError, match="transport retries"):
        asyncio.run(
            fetch_and_close(
                make_transport(
                    always_timeout,
                    transport_config=config(max_attempts=2),
                )
            )
        )
    assert timeout_calls == 2


def test_invalid_json_and_nonobject_fail_closed() -> None:
    def invalid_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    with raises(BlsPayloadError, match="valid JSON"):
        asyncio.run(fetch_and_close(make_transport(invalid_json)))

    def array_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with raises(BlsPayloadError, match="JSON object"):
        asyncio.run(fetch_and_close(make_transport(array_json)))


def test_rate_and_daily_budgets_are_project_local_and_fail_closed() -> None:
    clock = FakeClock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=successful_response())

    transport = make_transport(
        handler,
        clock=clock,
        transport_config=config(max_requests_per_day=2),
    )

    async def run_three_times() -> None:
        try:
            await transport.get_series(_REQUEST)
            await transport.get_series(_REQUEST)
            with raises(BlsRateLimitError, match="daily request budget"):
                await transport.get_series(_REQUEST)
        finally:
            await transport.aclose()

    asyncio.run(run_three_times())

    assert calls == 2
    assert clock.delays == [2.0]


def test_daily_budget_resets_only_on_a_new_utc_day() -> None:
    moments = iter((_NOW, _NOW, _NOW + timedelta(days=1), _NOW + timedelta(days=1)))
    calls = 0

    def utc_now() -> datetime:
        return next(moments)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=successful_response())

    transport = make_transport(
        handler,
        transport_config=config(max_requests_per_day=1),
        utc_now=utc_now,
    )

    async def run_twice() -> None:
        try:
            await transport.get_series(_REQUEST)
            await transport.get_series(_REQUEST)
        finally:
            await transport.aclose()

    asyncio.run(run_twice())
    assert calls == 2


def test_response_byte_and_content_length_limits_fail_closed() -> None:
    raw_body = b'{"value":"' + (b"x" * 2048) + b'"}'

    def oversized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=raw_body)

    with raises(BlsPayloadError, match="byte limit"):
        asyncio.run(
            fetch_and_close(
                make_transport(
                    oversized,
                    transport_config=config(max_response_bytes=1024),
                )
            )
        )

    for declared_length, message in (("invalid", "invalid"), ("-1", "negative")):
        def bad_length(
            request: httpx.Request,
            value: str = declared_length,
        ) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"{}",
                headers={"Content-Length": value},
            )

        with raises(BlsPayloadError, match=message):
            asyncio.run(fetch_and_close(make_transport(bad_length)))


def test_naive_transport_clock_fails_closed() -> None:
    transport = make_transport(
        lambda request: httpx.Response(200, json=successful_response()),
        utc_now=lambda: datetime(2026, 7, 31, 12, 0),
    )
    with raises(BlsTransportError, match="timezone-aware"):
        asyncio.run(fetch_and_close(transport))
