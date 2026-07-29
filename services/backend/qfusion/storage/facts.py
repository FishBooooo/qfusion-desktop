"""Point-in-Time facts in DuckDB with immutable Parquet batch archives."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import Final
from uuid import UUID, uuid4

import duckdb

from qfusion.domain import DataSourceRecord, FactQuery, require_point_in_time

_WAREHOUSE_SCHEMA_VERSION: Final = "1"
_SCHEMA_SQL: Final = """
CREATE TABLE IF NOT EXISTS warehouse_metadata (
    metadata_key VARCHAR PRIMARY KEY,
    metadata_value VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS source_facts (
    fact_id VARCHAR PRIMARY KEY,
    instrument_id VARCHAR,
    fact_type VARCHAR NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    batch_id VARCHAR NOT NULL,
    record_json VARCHAR NOT NULL,
    content_sha256 VARCHAR NOT NULL CHECK (length(content_sha256) = 64)
);
CREATE INDEX IF NOT EXISTS source_facts_available_at_idx
    ON source_facts (available_at);
CREATE INDEX IF NOT EXISTS source_facts_instrument_idx
    ON source_facts (instrument_id, available_at);
CREATE INDEX IF NOT EXISTS source_facts_type_idx
    ON source_facts (fact_type, available_at);
CREATE TABLE IF NOT EXISTS fact_batches (
    batch_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    record_count BIGINT NOT NULL CHECK (record_count > 0),
    parquet_relative_path VARCHAR NOT NULL UNIQUE,
    parquet_sha256 VARCHAR NOT NULL CHECK (length(parquet_sha256) = 64)
);
"""


class DuplicateFactError(ValueError):
    """Raised when an immutable fact identifier already exists."""


class FactIntegrityError(ValueError):
    """Raised when stored fact or archive content fails validation."""


@dataclass(frozen=True, slots=True)
class FactBatchReceipt:
    """Auditable result of one committed single-writer batch."""

    batch_id: UUID
    created_at: datetime
    record_count: int
    parquet_path: Path
    parquet_sha256: str


@dataclass(slots=True)
class _WriteRequest:
    records: tuple[DataSourceRecord, ...]
    future: asyncio.Future[FactBatchReceipt]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_record(record: DataSourceRecord) -> tuple[str, str]:
    serialized = json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(
        serialized.encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()
    return serialized, fingerprint


def _sql_string(value: str) -> str:
    """Quote a trusted, already validated local path or generated identifier."""

    return "'" + value.replace("'", "''") + "'"


def _resolve_existing_directory(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"{label} must be an existing non-symlink directory")
    normalized = Path(os.path.abspath(path))
    resolved = path.resolve(strict=True)
    if os.path.normcase(str(normalized)) != os.path.normcase(str(resolved)):
        raise ValueError(f"{label} must not traverse a symlink")
    return resolved


def _resolve_database_path(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("database_path must be absolute")
    parent = _resolve_existing_directory(path.parent, "database parent")
    unresolved = parent / path.name
    if unresolved.exists() and (not unresolved.is_file() or unresolved.is_symlink()):
        raise ValueError("database_path must identify a regular non-symlink file")
    return unresolved


def _resolve_regular_file(root: Path, relative: PurePosixPath, label: str) -> Path:
    candidate = root.joinpath(*relative.parts)
    if not candidate.is_file() or candidate.is_symlink():
        raise FactIntegrityError(f"{label} must be a regular non-symlink file")
    normalized = Path(os.path.abspath(candidate))
    resolved = candidate.resolve(strict=True)
    if (
        os.path.normcase(str(normalized)) != os.path.normcase(str(resolved))
        or not resolved.is_relative_to(root)
    ):
        raise FactIntegrityError(f"{label} escaped its storage root")
    return resolved


def _relative_archive_path(value: object, batch_id: UUID) -> PurePosixPath:
    expected = PurePosixPath("batches") / f"{batch_id}.parquet"
    if not isinstance(value, str) or value != expected.as_posix():
        raise FactIntegrityError("fact batch contains an unsafe or mismatched Parquet path")
    return expected


def _validate_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FactIntegrityError(f"{label} is not a lowercase SHA-256 digest")
    return value


class DuckDBFactRepository:
    """Store immutable source facts through one process-local writer boundary."""

    def __init__(self, database_path: Path, parquet_root: Path) -> None:
        self._database_path = _resolve_database_path(database_path)
        self._parquet_root = _resolve_existing_directory(parquet_root, "parquet_root")
        temporary_root = self._parquet_root / ".tmp"
        temporary_root.mkdir(mode=0o700, exist_ok=True)
        self._temporary_root = _resolve_existing_directory(
            temporary_root,
            "Parquet temporary directory",
        )
        extension_root = self._temporary_root / "extensions"
        extension_root.mkdir(mode=0o700, exist_ok=True)
        self._extension_root = _resolve_existing_directory(
            extension_root,
            "DuckDB extension directory",
        )
        self._write_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Create and validate the initial warehouse schema through the writer lock."""

        async with self._write_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._initialize_sync)
            self._initialized = True

    async def add_batch(
        self,
        records: Sequence[DataSourceRecord],
    ) -> FactBatchReceipt:
        """Atomically persist one immutable batch and its Parquet archive."""

        selected = tuple(records)
        if not selected:
            raise ValueError("fact batch must not be empty")
        fact_ids = [record.fact_id for record in selected]
        if len(fact_ids) != len(set(fact_ids)):
            raise DuplicateFactError("fact batch contains duplicate fact_id values")
        self._require_initialized()

        async with self._write_lock:
            return await asyncio.to_thread(self._add_batch_sync, selected)

    async def list_as_of(self, query: FactQuery) -> Sequence[DataSourceRecord]:
        """Return only validated records available at the decision time."""

        self._require_initialized()
        records = await asyncio.to_thread(self._list_as_of_sync, query)
        return require_point_in_time(query, records)

    async def get_batch_receipt(self, batch_id: UUID) -> FactBatchReceipt | None:
        """Return and audit one committed Parquet batch receipt."""

        self._require_initialized()
        return await asyncio.to_thread(self._get_batch_receipt_sync, batch_id)

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("DuckDB fact repository must be initialized before use")

    def _connect(self) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect(str(self._database_path))
        allowed_directory = _sql_string(str(self._parquet_root))
        temporary_directory = _sql_string(str(self._temporary_root / "duckdb.tmp"))
        extension_directory = _sql_string(str(self._extension_root))
        try:
            connection.execute("SET autoinstall_known_extensions = false")
            connection.execute("SET autoload_known_extensions = false")
            connection.execute("SET allow_community_extensions = false")
            connection.execute(f"SET extension_directory = {extension_directory}")
            connection.execute("LOAD parquet")
            connection.execute(f"SET allowed_directories = [{allowed_directory}]")
            connection.execute(f"SET temp_directory = {temporary_directory}")
            connection.execute("SET threads = 1")
            connection.execute("SET enable_external_access = false")
            connection.execute("SET lock_configuration = true")
        except Exception:
            connection.close()
            raise
        return connection

    def _initialize_sync(self) -> None:
        connection = self._connect()
        try:
            connection.execute(_SCHEMA_SQL)
            row = connection.execute(
                "SELECT metadata_value FROM warehouse_metadata WHERE metadata_key = ?",
                ["schema_version"],
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO warehouse_metadata VALUES (?, ?)",
                    ["schema_version", _WAREHOUSE_SCHEMA_VERSION],
                )
            elif row[0] != _WAREHOUSE_SCHEMA_VERSION:
                raise FactIntegrityError(
                    f"unsupported DuckDB warehouse schema version: {row[0]!r}"
                )
        finally:
            connection.close()

    def _add_batch_sync(
        self,
        records: tuple[DataSourceRecord, ...],
    ) -> FactBatchReceipt:
        batch_id = uuid4()
        created_at = datetime.now(UTC)
        relative_path = PurePosixPath("batches") / f"{batch_id}.parquet"
        batch_root = self._parquet_root / "batches"
        batch_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        resolved_batch_root = _resolve_existing_directory(batch_root, "Parquet batch directory")
        final_path = resolved_batch_root / relative_path.name
        temporary_path = self._temporary_root / f"{batch_id}.parquet.part"
        if final_path.exists() or temporary_path.exists():
            raise FactIntegrityError("generated Parquet batch path already exists")

        rows: list[tuple[object, ...]] = []
        for record in records:
            serialized, fingerprint = _canonical_record(record)
            rows.append(
                (
                    str(record.fact_id),
                    None if record.instrument_id is None else str(record.instrument_id),
                    record.fact_type,
                    record.available_at,
                    str(batch_id),
                    serialized,
                    fingerprint,
                )
            )

        connection = self._connect()
        transaction_open = False
        moved_archive = False
        archive_sha256 = ""
        try:
            connection.execute("BEGIN TRANSACTION")
            transaction_open = True
            connection.executemany(
                """
                INSERT INTO source_facts (
                    fact_id, instrument_id, fact_type, available_at,
                    batch_id, record_json, content_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.execute(
                f"""
                COPY (
                    SELECT fact_id, instrument_id, fact_type, available_at,
                           batch_id, record_json, content_sha256
                    FROM source_facts
                    WHERE batch_id = {_sql_string(str(batch_id))}
                    ORDER BY fact_id
                ) TO {_sql_string(str(temporary_path))}
                (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
            if not temporary_path.is_file() or temporary_path.is_symlink():
                raise FactIntegrityError("DuckDB did not create a regular Parquet archive")
            archived_count = connection.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(temporary_path)],
            ).fetchone()
            if archived_count is None or archived_count[0] != len(records):
                raise FactIntegrityError("Parquet archive row count does not match the batch")
            archive_sha256 = _sha256(temporary_path)
            os.replace(temporary_path, final_path)
            moved_archive = True
            connection.execute(
                """
                INSERT INTO fact_batches (
                    batch_id, created_at, record_count,
                    parquet_relative_path, parquet_sha256
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    str(batch_id),
                    created_at,
                    len(records),
                    relative_path.as_posix(),
                    archive_sha256,
                ],
            )
            connection.execute("COMMIT")
            transaction_open = False
        except duckdb.ConstraintException as error:
            try:
                if transaction_open:
                    connection.execute("ROLLBACK")
            finally:
                self._remove_failed_archive(temporary_path, final_path, moved_archive)
            raise DuplicateFactError("one or more fact_id values already exist") from error
        except Exception:
            try:
                if transaction_open:
                    connection.execute("ROLLBACK")
            finally:
                self._remove_failed_archive(temporary_path, final_path, moved_archive)
            raise
        finally:
            connection.close()

        return FactBatchReceipt(
            batch_id=batch_id,
            created_at=created_at,
            record_count=len(records),
            parquet_path=final_path,
            parquet_sha256=archive_sha256,
        )

    @staticmethod
    def _remove_failed_archive(
        temporary_path: Path,
        final_path: Path,
        moved_archive: bool,
    ) -> None:
        temporary_path.unlink(missing_ok=True)
        if moved_archive:
            final_path.unlink(missing_ok=True)

    def _list_as_of_sync(self, query: FactQuery) -> tuple[DataSourceRecord, ...]:
        predicates = ["available_at <= ?"]
        parameters: list[object] = [query.decision_time]
        if query.instrument_ids:
            placeholders = ", ".join("?" for _ in query.instrument_ids)
            predicates.append(f"instrument_id IN ({placeholders})")
            parameters.extend(str(value) for value in query.instrument_ids)
        if query.fact_types:
            placeholders = ", ".join("?" for _ in query.fact_types)
            predicates.append(f"fact_type IN ({placeholders})")
            parameters.extend(query.fact_types)

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT fact_id, instrument_id, fact_type, available_at,
                       record_json, content_sha256
                FROM source_facts WHERE
                """
                + " AND ".join(predicates)
                + " ORDER BY available_at, fact_id",
                parameters,
            ).fetchall()
        finally:
            connection.close()

        restored: list[DataSourceRecord] = []
        for fact_id, instrument_id, fact_type, available_at, record_json, fingerprint in rows:
            expected_fingerprint = _validate_sha256(fingerprint, "stored fact fingerprint")
            if not isinstance(record_json, str):
                raise FactIntegrityError("stored fact JSON is not text")
            actual_fingerprint = hashlib.sha256(
                record_json.encode("utf-8"),
                usedforsecurity=False,
            ).hexdigest()
            if actual_fingerprint != expected_fingerprint:
                raise FactIntegrityError("stored fact fingerprint does not match its content")
            try:
                record = DataSourceRecord.model_validate_json(record_json)
            except ValueError as error:
                raise FactIntegrityError(
                    "stored fact no longer satisfies the domain contract"
                ) from error
            expected_instrument = (
                None if record.instrument_id is None else str(record.instrument_id)
            )
            if (
                fact_id != str(record.fact_id)
                or instrument_id != expected_instrument
                or fact_type != record.fact_type
                or available_at != record.available_at
            ):
                raise FactIntegrityError("stored fact index columns differ from canonical JSON")
            restored.append(record)
        return tuple(restored)

    def _get_batch_receipt_sync(self, batch_id: UUID) -> FactBatchReceipt | None:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT created_at, record_count, parquet_relative_path, parquet_sha256
                FROM fact_batches WHERE batch_id = ?
                """,
                [str(batch_id)],
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None

        created_at, record_count, relative_value, sha256_value = row
        if (
            not isinstance(created_at, datetime)
            or created_at.tzinfo is None
            or created_at.utcoffset() is None
            or not isinstance(record_count, int)
            or record_count <= 0
        ):
            raise FactIntegrityError("fact batch metadata is invalid")
        expected_sha256 = _validate_sha256(sha256_value, "Parquet archive fingerprint")
        relative_path = _relative_archive_path(relative_value, batch_id)
        archive_path = _resolve_regular_file(
            self._parquet_root,
            relative_path,
            "Parquet archive",
        )
        if _sha256(archive_path) != expected_sha256:
            raise FactIntegrityError("fact batch Parquet archive failed its SHA-256 audit")

        connection = self._connect()
        try:
            count_row = connection.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(archive_path)],
            ).fetchone()
        finally:
            connection.close()
        if count_row is None or count_row[0] != record_count:
            raise FactIntegrityError("fact batch Parquet archive row count is invalid")

        return FactBatchReceipt(
            batch_id=batch_id,
            created_at=created_at.astimezone(UTC),
            record_count=record_count,
            parquet_path=archive_path,
            parquet_sha256=expected_sha256,
        )


class FactWriteQueue:
    """Serialize all fact writes through one owned asynchronous queue."""

    def __init__(self, repository: DuckDBFactRepository) -> None:
        self._repository = repository
        self._queue: asyncio.Queue[_WriteRequest | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._accepting = False

    async def __aenter__(self) -> FactWriteQueue:
        if self._worker is not None:
            raise RuntimeError("fact write queue is already running")
        self._accepting = True
        self._worker = asyncio.create_task(self._run(), name="qfusion-fact-writer")
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        await self.close()

    async def submit(
        self,
        records: Sequence[DataSourceRecord],
    ) -> FactBatchReceipt:
        if not self._accepting or self._worker is None or self._worker.done():
            raise RuntimeError("fact write queue is not running")
        future: asyncio.Future[FactBatchReceipt] = asyncio.get_running_loop().create_future()
        self._queue.put_nowait(_WriteRequest(tuple(records), future))
        return await future

    async def close(self) -> None:
        worker = self._worker
        if worker is None:
            return
        if self._accepting:
            self._accepting = False
            self._queue.put_nowait(None)
        try:
            await worker
        finally:
            self._worker = None

    async def _run(self) -> None:
        while True:
            request = await self._queue.get()
            try:
                if request is None:
                    return
                try:
                    receipt = await self._repository.add_batch(request.records)
                except Exception as error:
                    if not request.future.done():
                        request.future.set_exception(error)
                else:
                    if not request.future.done():
                        request.future.set_result(receipt)
            finally:
                self._queue.task_done()
