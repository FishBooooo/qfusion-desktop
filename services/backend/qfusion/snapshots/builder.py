"""Deterministic Point-in-Time analysis snapshot construction."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qfusion.domain import (
    MARKET_TIMEZONES,
    AnalysisSnapshot,
    DataSourceRecord,
    FactQuery,
    FactReadRepository,
    Market,
    QualityFlag,
    RequestedHorizon,
    SnapshotRepository,
    TargetType,
    require_point_in_time,
)


class SnapshotBuildError(ValueError):
    """Raised when facts cannot form one unambiguous analysis snapshot."""


class SnapshotDataCategory(StrEnum):
    """Top-level freshness categories represented by AnalysisSnapshot."""

    PRICE = "price"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    OPTIONS = "options"
    MACRO = "macro"
    FLOW = "flow"


class SnapshotFactRule(BaseModel):
    """Map one explicit vendor-neutral fact type to a snapshot category."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fact_type: str = Field(min_length=1, max_length=128)
    category: SnapshotDataCategory


class SnapshotFreshnessRule(BaseModel):
    """Optional maximum observation age for one category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: SnapshotDataCategory
    max_age: timedelta

    @field_validator("max_age")
    @classmethod
    def require_positive_age(cls, value: timedelta) -> timedelta:
        if value <= timedelta(0):
            raise ValueError("max_age must be positive")
        return value


def _m1_fact_rules() -> tuple[SnapshotFactRule, ...]:
    return (
        SnapshotFactRule(
            fact_type="market.bar.daily",
            category=SnapshotDataCategory.PRICE,
        ),
        SnapshotFactRule(
            fact_type="market.bar.minute",
            category=SnapshotDataCategory.PRICE,
        ),
        SnapshotFactRule(
            fact_type="filing",
            category=SnapshotDataCategory.FUNDAMENTAL,
        ),
        SnapshotFactRule(
            fact_type="news",
            category=SnapshotDataCategory.NEWS,
        ),
    )


class SnapshotBuildPolicy(BaseModel):
    """Explicit fact selection, completeness, and freshness policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_rules: tuple[SnapshotFactRule, ...] = Field(default_factory=_m1_fact_rules)
    required_categories: tuple[SnapshotDataCategory, ...] = (
        SnapshotDataCategory.PRICE,
        SnapshotDataCategory.FUNDAMENTAL,
        SnapshotDataCategory.NEWS,
    )
    freshness_rules: tuple[SnapshotFreshnessRule, ...] = ()

    @model_validator(mode="after")
    def require_unambiguous_rules(self) -> Self:
        fact_types = tuple(rule.fact_type for rule in self.fact_rules)
        if not fact_types:
            raise ValueError("fact_rules must not be empty")
        if len(fact_types) != len(set(fact_types)):
            raise ValueError("fact_rules must use unique fact_type values")
        if not self.required_categories:
            raise ValueError("required_categories must not be empty")
        if len(self.required_categories) != len(set(self.required_categories)):
            raise ValueError("required_categories must be unique")

        mapped_categories = {rule.category for rule in self.fact_rules}
        unmapped = set(self.required_categories) - mapped_categories
        if unmapped:
            rendered = ", ".join(sorted(category.value for category in unmapped))
            raise ValueError(f"required categories lack fact rules: {rendered}")

        freshness_categories = tuple(rule.category for rule in self.freshness_rules)
        if len(freshness_categories) != len(set(freshness_categories)):
            raise ValueError("freshness_rules must use unique categories")
        if set(freshness_categories) - mapped_categories:
            raise ValueError("freshness_rules must reference mapped categories")
        return self

    def fact_category_map(self) -> dict[str, SnapshotDataCategory]:
        """Return a fresh mapping so callers cannot mutate policy state."""

        return {rule.fact_type: rule.category for rule in self.fact_rules}

    def freshness_map(self) -> dict[SnapshotDataCategory, timedelta]:
        """Return optional maximum ages by category."""

        return {rule.category: rule.max_age for rule in self.freshness_rules}


class SnapshotBuildRequest(BaseModel):
    """Validated target and time boundary for one snapshot build."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: TargetType
    target_id: UUID
    market: Market
    requested_horizon: RequestedHorizon
    decision_time: datetime
    instrument_ids: tuple[UUID, ...]

    @field_validator("decision_time")
    @classmethod
    def normalize_decision_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decision_time must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("instrument_ids")
    @classmethod
    def canonicalize_instrument_ids(cls, values: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not values:
            raise ValueError("instrument_ids must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("instrument_ids must be unique")
        return tuple(sorted(values, key=str))

    @model_validator(mode="after")
    def require_stock_identity_alignment(self) -> Self:
        if self.target_type is TargetType.STOCK and self.instrument_ids != (self.target_id,):
            raise ValueError("stock snapshots must query exactly their target_id")
        return self


_QUALITY_WEIGHTS: dict[QualityFlag, float] = {
    QualityFlag.OK: 1.0,
    QualityFlag.DELAYED: 0.75,
    QualityFlag.STALE: 0.5,
    QualityFlag.CONFLICT: 0.25,
    QualityFlag.MISSING: 0.0,
    QualityFlag.SYNTHETIC_MOCK: 0.5,
}
_AS_OF_FIELDS: dict[SnapshotDataCategory, str] = {
    SnapshotDataCategory.PRICE: "price_as_of",
    SnapshotDataCategory.FUNDAMENTAL: "fundamental_as_of",
    SnapshotDataCategory.NEWS: "news_as_of",
    SnapshotDataCategory.OPTIONS: "options_as_of",
    SnapshotDataCategory.MACRO: "macro_as_of",
    SnapshotDataCategory.FLOW: "flow_as_of",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _unique_versions(entries: Iterable[tuple[str, str]], label: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for key, value in entries:
        previous = versions.setdefault(key, value)
        if previous != value:
            raise SnapshotBuildError(
                f"conflicting {label} for {key!r}: {previous!r} versus {value!r}"
            )
    return dict(sorted(versions.items()))


class SnapshotBuilder:
    """Build and persist one immutable snapshot from a guarded fact repository."""

    def __init__(
        self,
        fact_repository: FactReadRepository,
        snapshot_repository: SnapshotRepository,
        *,
        policy: SnapshotBuildPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
        snapshot_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._fact_repository = fact_repository
        self._snapshot_repository = snapshot_repository
        self._policy = policy or SnapshotBuildPolicy()
        self._clock = clock
        self._snapshot_id_factory = snapshot_id_factory

    async def build(self, request: SnapshotBuildRequest) -> AnalysisSnapshot:
        """Select facts at decision_time, derive metadata, and persist the snapshot."""

        category_by_type = self._policy.fact_category_map()
        query = FactQuery(
            decision_time=request.decision_time,
            instrument_ids=request.instrument_ids,
            fact_types=tuple(category_by_type),
        )
        repository_records = tuple(await self._fact_repository.list_as_of(query))
        try:
            records = require_point_in_time(query, repository_records)
        except ValueError as error:
            raise SnapshotBuildError(
                "fact repository violated the requested Point-in-Time boundary"
            ) from error

        fact_ids = tuple(record.fact_id for record in records)
        if len(fact_ids) != len(set(fact_ids)):
            raise SnapshotBuildError("fact repository returned duplicate fact_id values")

        ordered = tuple(sorted(records, key=lambda item: (item.available_at, str(item.fact_id))))
        category_records = self._group_by_category(ordered, category_by_type)
        as_of_values, missing_data, stale_data, quality_score = self._assess_quality(
            request.decision_time,
            category_records,
        )
        provider_versions = _unique_versions(
            ((record.source, record.provider_version) for record in ordered),
            "provider versions",
        )
        dataset_versions = _unique_versions(
            (
                (f"{record.source}::{record.fact_type}", record.dataset_version)
                for record in ordered
            ),
            "dataset versions",
        )

        created_at = self._clock()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise SnapshotBuildError("snapshot clock must return a timezone-aware timestamp")
        created_at = created_at.astimezone(UTC)
        if created_at < request.decision_time:
            raise SnapshotBuildError("snapshot clock returned a time before decision_time")

        snapshot = AnalysisSnapshot(
            snapshot_id=self._snapshot_id_factory(),
            target_type=request.target_type,
            target_id=request.target_id,
            market=request.market,
            requested_horizon=request.requested_horizon,
            decision_time=request.decision_time,
            market_timezone=MARKET_TIMEZONES[request.market],
            created_at=created_at,
            provider_versions=provider_versions,
            dataset_versions=dataset_versions,
            fact_ids=tuple(record.fact_id for record in ordered),
            missing_data=missing_data,
            stale_data=stale_data,
            quality_score=quality_score,
            price_as_of=as_of_values["price_as_of"],
            fundamental_as_of=as_of_values["fundamental_as_of"],
            news_as_of=as_of_values["news_as_of"],
            options_as_of=as_of_values["options_as_of"],
            macro_as_of=as_of_values["macro_as_of"],
            flow_as_of=as_of_values["flow_as_of"],
        )
        await self._snapshot_repository.add(snapshot)
        return snapshot

    @staticmethod
    def _group_by_category(
        records: Sequence[DataSourceRecord],
        category_by_type: dict[str, SnapshotDataCategory],
    ) -> dict[SnapshotDataCategory, tuple[DataSourceRecord, ...]]:
        grouped: dict[SnapshotDataCategory, list[DataSourceRecord]] = {
            category: [] for category in SnapshotDataCategory
        }
        for record in records:
            try:
                category = category_by_type[record.fact_type]
            except KeyError as error:
                raise SnapshotBuildError(
                    f"fact repository returned unmapped fact type: {record.fact_type!r}"
                ) from error
            grouped[category].append(record)
        return {category: tuple(values) for category, values in grouped.items()}

    def _assess_quality(
        self,
        decision_time: datetime,
        grouped: dict[SnapshotDataCategory, tuple[DataSourceRecord, ...]],
    ) -> tuple[dict[str, datetime | None], tuple[str, ...], tuple[str, ...], float]:
        freshness_limits = self._policy.freshness_map()
        as_of_values: dict[str, datetime | None] = {}
        missing: set[SnapshotDataCategory] = set()
        stale: set[SnapshotDataCategory] = set()
        category_scores: dict[SnapshotDataCategory, float] = {}

        for category, field_name in _AS_OF_FIELDS.items():
            records = grouped[category]
            usable = tuple(
                record for record in records if record.quality_flag is not QualityFlag.MISSING
            )
            as_of = max((record.event_time for record in usable), default=None)
            as_of_values[field_name] = as_of

            if category in self._policy.required_categories and not usable:
                missing.add(category)
                category_scores[category] = 0.0
                continue
            if not usable:
                continue

            is_stale = any(record.quality_flag is QualityFlag.STALE for record in usable)
            maximum_age = freshness_limits.get(category)
            if maximum_age is not None and as_of is not None:
                is_stale = is_stale or decision_time - as_of > maximum_age
            if is_stale:
                stale.add(category)

            score = min(_QUALITY_WEIGHTS[record.quality_flag] for record in records)
            category_scores[category] = min(score, 0.5) if is_stale else score

        required_scores = (
            category_scores.get(category, 0.0)
            for category in self._policy.required_categories
        )
        quality_score = round(
            sum(required_scores) / len(self._policy.required_categories),
            6,
        )
        return (
            as_of_values,
            tuple(sorted(category.value for category in missing)),
            tuple(
                sorted(category.value for category in stale if category not in missing)
            ),
            quality_score,
        )
