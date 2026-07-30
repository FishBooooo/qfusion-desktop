"""Mock-transport tests for SEC DNS, redirects, retry, rate, and headers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

import httpx
from pytest import raises

from qfusion.providers.sec import (
    SecHttpTransport,
    SecNetworkPolicyError,
    SecPayloadError,
    SecTransportConfig,
    SecTransportError,
    require_public_addresses,
)

_NOW: Final = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


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


def config(**overrides: object) -> SecTransportConfig:
    values: dict[str, object] = {"user_agent": "QFusion CI ci@example.com"}
    values.update(overrides)
    return SecTransportConfig.model_validate(values)


async def fetch_and_close(transport: SecHttpTransport):
    try:
        return await transport.get_submissions("0000000001")
    finally:
        await transport.aclose()


def make_transport(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    resolver: StaticResolver | None = None,
    clock: FakeClock | None = None,
    transport_config: SecTransportConfig | None = None,
) -> SecHttpTransport:
    selected_clock = clock or FakeClock()
    return SecHttpTransport(
        transport_config or config(),
        resolver=resolver or StaticResolver(("93.184.216.34",)),
        http_transport=httpx.MockTransport(handler),
        sleep=selected_clock.sleep,
        monotonic=selected_clock.monotonic,
        utc_now=lambda: _NOW,
    )


def test_public_address_policy_rejects_empty_private_local_and_invalid_results() -> None:
    with raises(SecNetworkPolicyError, match="no addresses"):
        require_public_addresses("data.sec.gov", ())
    for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "invalid"):
        with raises(SecNetworkPolicyError):
            require_public_addresses("data.sec.gov", (address,))


def test_success_uses_fixed_host_path_declared_headers_and_receipt_time() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"cik": 1, "name": "TEST", "filings": {}})

    response = asyncio.run(fetch_and_close(make_transport(handler)))

    assert response.received_at == _NOW
    assert response.payload["cik"] == 1
    assert len(requests) == 1
    assert requests[0].url == httpx.URL(
        "https://data.sec.gov/submissions/CIK0000000001.json"
    )
    assert requests[0].headers["User-Agent"] == "QFusion CI ci@example.com"
    assert requests[0].headers["Accept"] == "application/json"


def test_private_dns_blocks_before_http_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    transport = make_transport(
        handler,
        resolver=StaticResolver(("127.0.0.1",)),
    )
    with raises(SecNetworkPolicyError):
        asyncio.run(fetch_and_close(transport))
    assert calls == 0


def test_redirect_is_never_followed() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/private"},
        )

    with raises(SecTransportError, match="redirects"):
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
        return httpx.Response(200, json={"cik": 1})

    response = asyncio.run(
        fetch_and_close(
            make_transport(
                handler,
                clock=clock,
                transport_config=config(max_retry_delay_seconds=1.5),
            )
        )
    )

    assert response.payload["cik"] == 1
    assert calls == 2
    assert 1.5 in clock.delays


def test_transport_errors_retry_but_nonretryable_status_does_not() -> None:
    timeout_calls = 0
    clock = FakeClock()

    def timeout_then_success(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        if timeout_calls == 1:
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(200, json={"cik": 1})

    assert asyncio.run(
        fetch_and_close(make_transport(timeout_then_success, clock=clock))
    ).payload["cik"] == 1
    assert timeout_calls == 2
    assert clock.delays

    not_found_calls = 0

    def not_found(request: httpx.Request) -> httpx.Response:
        nonlocal not_found_calls
        not_found_calls += 1
        return httpx.Response(404)

    with raises(SecTransportError, match="HTTP 404"):
        asyncio.run(fetch_and_close(make_transport(not_found)))
    assert not_found_calls == 1


def test_exhausted_status_and_transport_retries_raise_typed_errors() -> None:
    status_calls = 0

    def unavailable(request: httpx.Request) -> httpx.Response:
        nonlocal status_calls
        status_calls += 1
        return httpx.Response(503)

    with raises(SecTransportError, match="exhausted retries"):
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

    with raises(SecTransportError, match="transport retries"):
        asyncio.run(
            fetch_and_close(
                make_transport(
                    always_timeout,
                    transport_config=config(max_attempts=2),
                )
            )
        )
    assert timeout_calls == 2


def test_invalid_json_nonobject_and_invalid_cik_fail_closed() -> None:
    def invalid_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )

    with raises(SecPayloadError, match="valid JSON"):
        asyncio.run(fetch_and_close(make_transport(invalid_json)))

    def array_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with raises(SecPayloadError, match="JSON object"):
        asyncio.run(fetch_and_close(make_transport(array_json)))

    transport = make_transport(lambda request: httpx.Response(200, json={}))
    try:
        with raises(ValueError, match="ten-digit"):
            asyncio.run(transport.get_submissions("1"))
    finally:
        asyncio.run(transport.aclose())


def test_rate_limiter_serializes_consecutive_requests_at_five_per_second() -> None:
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"cik": 1})

    transport = make_transport(handler, clock=clock)

    async def run_twice() -> None:
        try:
            await transport.get_submissions("0000000001")
            await transport.get_submissions("0000000001")
        finally:
            await transport.aclose()

    asyncio.run(run_twice())

    assert clock.delays == [0.2]
