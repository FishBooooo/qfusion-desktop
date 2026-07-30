"""Structural interfaces implemented by all external data adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from qfusion.domain import DataSourceRecord
from qfusion.providers.contracts import (
    ProviderAccessProfile,
    ProviderBarRequest,
    ProviderCapability,
)


@runtime_checkable
class ProviderAdapter(Protocol):
    """Expose immutable implementation capability and observed account access."""

    @property
    def capability(self) -> ProviderCapability:
        """Return the adapter's versioned technical capability."""
        ...

    @property
    def access_profile(self) -> ProviderAccessProfile:
        """Return the current account entitlement and observed data quality."""
        ...


@runtime_checkable
class MarketDataProvider(ProviderAdapter, Protocol):
    """Read market data without leaking vendor SDK types into application code."""

    async def get_bars(self, request: ProviderBarRequest) -> Sequence[DataSourceRecord]:
        """Return traceable bars available by the request's decision time."""
        ...
