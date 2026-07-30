"""Fixed-origin, no-proxy HTTP transport for SEC public JSON APIs."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol, cast

import httpx
from pydantic import JsonValue, ValidationError

from qfusion.providers.sec.contracts import SecJsonResponse, SecTransportConfig
from qfusion.providers.sec.errors import (
    SecNetworkPolicyError,
    SecPayloadError,
    SecTransportError,
)

_SEC_HOST = "data.sec.gov"
_SEC_BASE_URL = f"https://{_SEC_HOST}"
_CIK_PATTERN = re.compile(r"^\d{10}$")
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
Sleep = Callable[[float], Awaitable[None]]
Monotonic = Callable[[], float]
UtcNow = Callable[[], datetime]


class HostResolver(Protocol):
    """Resolve a fixed public hostname without exposing arbitrary URL input."""

    async def resolve(self, host: str) -> tuple[str, ...]:
        """Return every address observed for the hostname."""
        ...


class SecJsonTransport(Protocol):
    """Minimal transport consumed by the SEC Adapter and replaced by CI fakes."""

    async def get_submissions(self, cik: str) -> SecJsonResponse:
        """Fetch one submissions JSON object for a validated ten-digit CIK."""
        ...


class DefaultPublicResolver:
    """Resolve the fixed SEC host through the operating-system resolver."""

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


def require_public_addresses(host: str, addresses: tuple[str, ...]) -> None:
    """Reject empty, malformed, private, local, link-local, or reserved DNS results."""

    if not addresses:
        raise SecNetworkPolicyError(f"{host} resolved to no addresses")
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as error:
            raise SecNetworkPolicyError(
                f"{host} resolved to an invalid IP address"
            ) from error
        if not parsed.is_global:
            raise SecNetworkPolicyError(
                f"{host} resolved to a non-public address"
            )


class SecHttpTransport:
    """HTTPX transport with fixed host, bounded retry, and fail-closed DNS policy."""

    def __init__(
        self,
        config: SecTransportConfig,
        *,
        resolver: HostResolver | None = None,
        http_transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        monotonic: Monotonic = time.monotonic,
        utc_now: UtcNow | None = None,
    ) -> None:
        self._config = config
        self._resolver = resolver or DefaultPublicResolver()
        self._sleep = sleep
        self._monotonic = monotonic
        self._utc_now = utc_now or (lambda: datetime.now(UTC))
        self._next_request_at = 0.0
        self._request_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            base_url=_SEC_BASE_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": config.user_agent,
            },
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=http_transport,
        )

    async def __aenter__(self) -> SecHttpTransport:
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

    async def _wait_for_rate_slot(self) -> None:
        now = self._monotonic()
        delay = self._next_request_at - now
        if delay > 0:
            await self._sleep(delay)
            now = self._monotonic()
        interval = 1.0 / self._config.max_requests_per_second
        self._next_request_at = max(now, self._next_request_at) + interval

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
                raise SecPayloadError(
                    "SEC response Content-Length was invalid"
                ) from error
            if parsed_length < 0:
                raise SecPayloadError("SEC response Content-Length was negative")
            if parsed_length > self._config.max_response_bytes:
                raise SecPayloadError(
                    "SEC response body exceeded the configured byte limit"
                )

        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > self._config.max_response_bytes:
                raise SecPayloadError(
                    "SEC response body exceeded the configured byte limit"
                )
            body.extend(chunk)
        return bytes(body)

    async def get_submissions(self, cik: str) -> SecJsonResponse:
        """Fetch a fixed submissions path; redirects and non-public DNS fail closed."""

        if _CIK_PATTERN.fullmatch(cik) is None:
            raise ValueError("SEC transport requires an exact ten-digit CIK")

        path = f"/submissions/CIK{cik}.json"
        last_transport_error: httpx.TransportError | None = None

        async with self._request_lock:
            for attempt in range(self._config.max_attempts):
                addresses = await self._resolver.resolve(_SEC_HOST)
                require_public_addresses(_SEC_HOST, addresses)
                await self._wait_for_rate_slot()

                response: httpx.Response | None = None
                retry_delay: float | None = None
                try:
                    request = self._client.build_request("GET", path)
                    response = await self._client.send(request, stream=True)
                    try:
                        if 300 <= response.status_code < 400:
                            raise SecTransportError("SEC redirects are not permitted")
                        if response.status_code == 200:
                            raw_body = await self._read_bounded_body(response)
                            try:
                                decoded: object = json.loads(raw_body)
                            except (
                                json.JSONDecodeError,
                                UnicodeDecodeError,
                            ) as error:
                                raise SecPayloadError(
                                    "SEC response body was not valid JSON"
                                ) from error
                            if not isinstance(decoded, dict) or not all(
                                isinstance(key, str) for key in decoded
                            ):
                                raise SecPayloadError(
                                    "SEC response body must be a JSON object"
                                )
                            payload = cast(dict[str, JsonValue], decoded)
                            try:
                                return SecJsonResponse(
                                    payload=payload,
                                    raw_body=raw_body,
                                    received_at=self._utc_now(),
                                    content_type=response.headers.get("Content-Type"),
                                    etag=response.headers.get("ETag"),
                                    last_modified=response.headers.get("Last-Modified"),
                                )
                            except ValidationError as error:
                                raise SecPayloadError(
                                    "SEC response envelope failed validation"
                                ) from error

                        if response.status_code not in _RETRYABLE_STATUS:
                            raise SecTransportError(
                                f"SEC request failed with HTTP {response.status_code}"
                            )
                        if attempt + 1 >= self._config.max_attempts:
                            raise SecTransportError(
                                "SEC request exhausted retries with HTTP "
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

        raise SecTransportError("SEC request exhausted transport retries") from last_transport_error
