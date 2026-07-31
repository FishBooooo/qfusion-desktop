"""Structural BLS interface kept free of concrete transport details."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from qfusion.domain import DataSourceRecord
from qfusion.providers.bls.contracts import BlsSeriesRequest
from qfusion.providers.interfaces import ProviderAdapter


@runtime_checkable
class BlsMacroSeriesProvider(ProviderAdapter, Protocol):
    """Read monthly BLS observations through the credential-free v1 boundary."""

    async def get_series(
        self,
        request: BlsSeriesRequest,
    ) -> Sequence[DataSourceRecord]:
        """Return first-observed macro facts for persistence and later snapshots."""
        ...
