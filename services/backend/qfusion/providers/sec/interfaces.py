"""Structural SEC filing interface kept free of concrete transport details."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from qfusion.domain import DataSourceRecord
from qfusion.providers.interfaces import ProviderAdapter
from qfusion.providers.sec.contracts import SecFilingRequest


@runtime_checkable
class SecFilingProvider(ProviderAdapter, Protocol):
    """Read registry-resolved SEC filing metadata."""

    async def get_filings(
        self,
        request: SecFilingRequest,
    ) -> Sequence[DataSourceRecord]:
        """Return Point-in-Time-safe SEC filing metadata."""
        ...
