"""Fixed-origin, no-proxy HTTP transport for the BLS Public Data API v1."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Protocol, cast

import httpx
from pydantic import JsonValue, ValidationError

from qfusion.providers.bls.contracts import (
    BlsJsonResponse,
    BlsSeriesRequest,
    BlsTransportConfig,
)
from qfusion.providers.bls.errors import (
    BlsNetworkPolicyError,
    BlsPayloadError,
    BlsRateLimitError,
    BlsTransportError,
)

_BLS_HOST = "api.bls.gov"
_BLS_BASE_URL = f"https://{_BLS_HOST}"
_BLS_SERIES_PATH = "/publicAPI/v1/timeseries/data/"
_RETRYABLE_STATUS = frozenset({202, 429, 500, 502, 503, 504})
Sleep = Callable[[float], Awaitable[None]]
Monotonic = Callable[[], float]
UtcNow = Callable[[], datetime]


class BlsResolver(Protocol):
    """Resolve the fixed BLS host without exposing arbitrary URL input."""

    async def resolve(self, host: str) -> tuple[str, ...]:
        """Return every address observed for the hostname."""
        ...


class BlsJsonTransport(Protocol):
    """Minimal transport consumed by the BLS Adapter and replaced by CI fakes."""

    async def get_series(self, request: BlsSeriesRequest) -> BlsJsonResponse:
        """Fetch one bounded, credential-free BLS v1 response."""
        ...


class BlsPublicResolver:
    """Resolve the fixed BLS host through the operating-system resolver."""

    async def resolve(self, host: str) -> tuple[str, ...]:
        results = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            443,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
        addresses = {str(item[4][0]) for item in results}
        return tuple(sorted(addresses))


def require_bls_public_addresses(host: str, addresses: tuple[str, ...]) -> None:
    """Reject empty, malformed, private, local, link-local, or reserved DNS results."""

    if not addresses:
        raise BlsNetworkPolicyError(f"{host} resolved to no addresses")
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as error:
            raise BlsNetworkPolicyError(
                f"{host} resolved to an invalid IP address"
            ) from error
        if not parsed.is_global:
            raise BlsNetworkPolicyError(f"{host} resolved to a non-public address")


class BlsHttpTransport:
    """HTTPX transport with fixed host, bounded retries, and local request budgets."""

    def __init__(
        self,
        config: BlsTransportConfig,
        *,
        resolver: BlsResolver | None = None,
        http_transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        monotonic: Monotonic = time.monotonic,
        utc_now: UtcNow | None = None,
    ) -> None:
        self._config = config
        self._resolver = resolver or BlsPublicResolver()
        self._sleep = sleep
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(UTC))
        self._next_request_at = 0.0
        self._request_day: date | None = None
        self._requests_today = 0
        self._request_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            base_url=_BLS_BASE_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Content-Type": "application/json",
                "User-Agent": config.user_agent,
            },
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=http_transport,
        )

    async def __aenter__(self) -> BlsHttpTransport:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close project-owned HTTP resources."""

        await self._client.aclose()

    async def _consume_request_slot(self) -> None:
        request_day = self._utc_now().astimezone(UTC).date()
        if request_day != self._request_day:
            self._request_day = request_day
            self._requests_today = 0
        if self._requests_today >= self._config.max_requests_per_day:
            raise BlsRateLimitError(
                "unregistered BLS v1 daily request budget was exhausted"
            )

        now = self._monotonic()
        delay = self._next_request_at - now
        if delay > 0:
            await self._sleep(delay)
            now = self._monotonic()
        interval = 10.0 / self._config.max_requests_per_10_seconds
        self._next_request_at = max(now, self._next_request_at) + interval
        self._requests_today += 1

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    parsed = max(0.0, float(retry_after))
                except ValueError:
                    parsed = 0.0
                return float(min(parsed, self._config.max_retry_delay_seconds))
        exponential = 0.25 * (2**attempt)
        return float(min(exponential, self._config.max_retry_delay_seconds))

    async def _read_bounded_body(self, response: httpx.Response) -> bytes:
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None:
            try:
                parsed_length = int(declared_length)
            except ValueError as error:
                raise BlsPayloadError(
                    "BLS response Content-Length was invalid"
                ) from error
            if parsed_length < 0:
                raise BlsPayloadError("BLS response Content-Length was negative")
            if parsed_length > self._config.max_response_bytes:
                raise BlsPayloadError(
                    "BLS response body exceeded the configured byte limit"
                )

        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > self._config.max_response_bytes:
                raise BlsPayloadError(
                    "BLS response body exceeded the configured byte limit"
                )
            body.extend(chunk)
        return bytes(body)

    async def get_series(self, request: BlsSeriesRequest) -> BlsJsonResponse:
        """POST a fixed BLS v1 path; redirects and non-public DNS fail closed."""

        body = json.dumps(
            request.api_payload(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        last_transport_error: httpx.TransportError | None = None

        async with self._request_lock:
            for attempt in range(self._config.max_attempts):
                addresses = await self._resolver.resolve(_BLS_HOST)
                require_bls_public_addresses(_BLS_HOST, addresses)
                await self._consume_request_slot()

                response: httpx.Response | None = None
                retry_delay: float | None = None
                try:
                    http_request = self._client.build_request(
                        "POST",
                        _BLS_SERIES_PATH,
                        content=body,
                    )
                    response = await self._client.send(http_request, stream=True)
                    try:
                        if 300 <= response.status_code < 400:
                            raise BlsTransportError("BLS redirects are not permitted")
                        if response.status_code == 200:
                            raw_body = await self._read_bounded_body(response)
                            try:
                                decoded: object = json.loads(raw_body)
                            except (
                                json.JSONDecodeError,
                                UnicodeDecodeError,
                            ) as error:
                                raise BlsPayloadError(
                                    "BLS response body was not valid JSON"
                                ) from error
                            if not isinstance(decoded, dict) or not all(
                                isinstance(key, str) for key in decoded
                            ):
                                raise BlsPayloadError(
                                    "BLS response body must be a JSON object"
                                )
                            payload = cast(dict[str, JsonValue], decoded)
                            try:
                                return BlsJsonResponse(
                                    payload=payload,
                                    raw_body=raw_body,
                                    received_at=self._utc_now(),
                                    content_type=response.headers.get("Content-Type"),
                                )
                            except ValidationError as error:
                                raise BlsPayloadError(
                                    "BLS response envelope failed validation"
                                ) from error

                        if response.status_code not in _RETRYABLE_STATUS:
                            raise BlsTransportError(
                                f"BLS request failed with HTTP {response.status_code}"
                            )
                        if attempt + 1 >= self._config.max_attempts:
                            raise BlsTransportError(
                                "BLS request exhausted retries with HTTP "
                                f"{response.status_code}"
                            )
                        retry_delay = self._retry_delay(attempt, response)
                    finally:
                        await response.aclose()
                except httpx.TransportError as error:
                    last_transport_error = error
                    if attempt + 1 >= self._config.max_attempts:
                        break
                    await self._sleep(self._retry_delay(attempt, None))
                    continue

                if retry_delay is not None:
                    await self._sleep(retry_delay)

        raise BlsTransportError("BLS request exhausted transport retries") from last_transport_error
