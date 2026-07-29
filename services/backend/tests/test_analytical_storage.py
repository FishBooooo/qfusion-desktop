"""M1-C analytical fact and raw-object storage tests."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import duckdb
import pytest

from qfusion.domain import DataSourceRecord, FactQuery, FactReadRepository, QualityFlag
from qfusion.storage.facts import (
    DuckDBFactRepository,
    DuplicateFactError,
    FactIntegrityError,
    FactWriteQueue,
)
from qfusion.storage.raw_store import ContentAddressedRawStore, RawStoreIntegrityError

_INSTRUMENT_A = UUID("10000000-0000-4000-8000-000000000001")
_INSTRUMENT_B = UUID("10000000-0000-4000-8000-000000000002")
_BASE_TIME = datetime(2026, 7, 29, 14, 0, tzinfo=UTC)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content, usedforsecurity=False).hexdigest()


def _record(
    sequence: int,
    fact_type: str,
    available_at: datetime,
    *,
    instrument_id: UUID = _INSTRUMENT_A,
) -> DataSourceRecord:
    raw_content = f"m1c-synthetic-mock-{sequence}-{fact_type}".encode()
    is_adjusted = fact_type == "market.bar.daily"
    return DataSourceRecord(
        fact_id=UUID(f"20000000-0000-4000-8000-{sequence:012d}"),
        instrument_id=instrument_id,
        fact_type=fact_type,
        source="M1-C Synthetic Mock",
        source_record_id=f"synthetic-{sequence}",
        source_quality_level="mock-contract-only",
        venue_scope="US synthetic fixture",
        license_scope="repository test fixture",
        provider_version="m1c.mock.1",
        dataset_version="2026-07-29",
        event_time=available_at - timedelta(minutes=3),
        published_at=available_at - timedelta(minutes=2),
        available_at=available_at,
        received_at=available_at + timedelta(minutes=1),
        ingested_at=available_at + timedelta(minutes=2),
        revision_id="original",
        quality_flag=QualityFlag.SYNTHETIC_MOCK,
        raw_payload_hash=_sha256(raw_content),
        is_adjusted=is_adjusted,
        adjustment_type="split-and-dividend" if is_adjusted else None,
        payload={
            "currency": "USD",
            "mock": True,
            "sequence": sequence,
            "value": 100.0 + sequence,
        },
    )


def _four_fact_fixture() -> tuple[DataSourceRecord, ...]:
    return (
        _record(1, "market.bar.daily", _BASE_TIME),
        _record(2, "market.bar.minute", _BASE_TIME + timedelta(minutes=5)),
        _record(3, "filing", _BASE_TIME + timedelta(hours=1)),
        _record(
            4,
            "news",
            _BASE_TIME + timedelta(hours=2),
            instrument_id=_INSTRUMENT_B,
        ),
    )


def _repository(base: Path) -> tuple[DuckDBFactRepository, Path, Path]:
    database_root = base / "database"
    parquet_root = base / "parquet"
    database_root.mkdir(parents=True)
    parquet_root.mkdir(parents=True)
    database_path = database_root / "warehouse.duckdb"
    return DuckDBFactRepository(database_path, parquet_root), database_path, parquet_root


def test_duckdb_fact_repository_round_trip_and_point_in_time(tmp_path: Path) -> None:
    repository, database_path, _ = _repository(tmp_path / "round-trip")
    records = _four_fact_fixture()

    async def scenario() -> None:
        await repository.initialize()
        await repository.initialize()
        assert isinstance(repository, FactReadRepository)

        async with FactWriteQueue(repository) as writer:
            receipt = await writer.submit(records)

        assert receipt.record_count == 4
        assert receipt.parquet_path.is_file()
        assert receipt.parquet_path.read_bytes()[:4] == b"PAR1"
        assert receipt.parquet_sha256 == _sha256(receipt.parquet_path.read_bytes())
        assert await repository.get_batch_receipt(receipt.batch_id) == receipt
        assert (
            await repository.get_batch_receipt(
                UUID("30000000-0000-4000-8000-000000000099")
            )
            is None
        )

        point_in_time = await repository.list_as_of(
            FactQuery(decision_time=_BASE_TIME + timedelta(hours=1, minutes=30))
        )
        assert [record.fact_type for record in point_in_time] == [
            "market.bar.daily",
            "market.bar.minute",
            "filing",
        ]

        minute_only = await repository.list_as_of(
            FactQuery(
                decision_time=_BASE_TIME + timedelta(hours=3),
                instrument_ids=(_INSTRUMENT_A,),
                fact_types=("market.bar.minute",),
            )
        )
        assert minute_only == (records[1],)

        second_instrument = await repository.list_as_of(
            FactQuery(
                decision_time=_BASE_TIME + timedelta(hours=3),
                instrument_ids=(_INSTRUMENT_B,),
            )
        )
        assert second_instrument == (records[3],)

        reopened = DuckDBFactRepository(database_path, receipt.parquet_path.parents[1])
        await reopened.initialize()
        assert await reopened.list_as_of(
            FactQuery(decision_time=_BASE_TIME + timedelta(hours=3))
        ) == records

    asyncio.run(scenario())

    connection = duckdb.connect(str(database_path))
    try:
        assert connection.execute(
            "SELECT metadata_value FROM warehouse_metadata WHERE metadata_key = 'schema_version'"
        ).fetchone() == ("1",)
        assert connection.execute("SELECT count(*) FROM source_facts").fetchone() == (4,)
        assert connection.execute("SELECT count(*) FROM fact_batches").fetchone() == (1,)
    finally:
        connection.close()


def test_fact_write_queue_serializes_and_survives_rejected_batches(tmp_path: Path) -> None:
    repository, _, parquet_root = _repository(tmp_path / "writer")
    first = _record(10, "market.bar.daily", _BASE_TIME)
    second = _record(11, "news", _BASE_TIME + timedelta(minutes=1))
    third = _record(12, "filing", _BASE_TIME + timedelta(minutes=2))

    async def scenario() -> None:
        await repository.initialize()
        writer = FactWriteQueue(repository)
        with pytest.raises(RuntimeError, match="not running"):
            await writer.submit((first,))

        async with writer:
            receipts = await asyncio.gather(
                writer.submit((first,)),
                writer.submit((second,)),
            )
            assert len({receipt.batch_id for receipt in receipts}) == 2

            with pytest.raises(DuplicateFactError, match="already exist"):
                await writer.submit((first,))
            with pytest.raises(DuplicateFactError, match="duplicate fact_id"):
                await writer.submit((third, third))
            with pytest.raises(ValueError, match="must not be empty"):
                await writer.submit(())

            third_receipt = await writer.submit((third,))
            assert third_receipt.record_count == 1

        await writer.close()
        with pytest.raises(RuntimeError, match="not running"):
            await writer.submit((third,))

        persisted = await repository.list_as_of(
            FactQuery(decision_time=_BASE_TIME + timedelta(hours=1))
        )
        assert persisted == (first, second, third)

    asyncio.run(scenario())
    assert len(tuple((parquet_root / "batches").glob("*.parquet"))) == 3
    assert tuple((parquet_root / ".tmp").glob("*.part")) == ()


def test_fact_repository_detects_database_and_archive_tampering(tmp_path: Path) -> None:
    repository, database_path, _ = _repository(tmp_path / "integrity")
    record = _record(20, "market.bar.minute", _BASE_TIME)

    async def persist() -> object:
        await repository.initialize()
        async with FactWriteQueue(repository) as writer:
            return await writer.submit((record,))

    receipt = asyncio.run(persist())
    assert hasattr(receipt, "batch_id")

    connection = duckdb.connect(str(database_path))
    try:
        row = connection.execute(
            """
            SELECT fact_type, record_json, content_sha256
            FROM source_facts WHERE fact_id = ?
            """,
            [str(record.fact_id)],
        ).fetchone()
        assert row is not None
        original_type, original_json, original_fingerprint = row

        connection.execute(
            "UPDATE source_facts SET content_sha256 = ? WHERE fact_id = ?",
            ["0" * 64, str(record.fact_id)],
        )
    finally:
        connection.close()

    with pytest.raises(FactIntegrityError, match="fingerprint does not match"):
        asyncio.run(repository.list_as_of(FactQuery(decision_time=_BASE_TIME)))

    connection = duckdb.connect(str(database_path))
    try:
        invalid_json = "{"
        connection.execute(
            """
            UPDATE source_facts SET record_json = ?, content_sha256 = ?
            WHERE fact_id = ?
            """,
            [_sha256(invalid_json.encode()), _sha256(invalid_json.encode()), str(record.fact_id)],
        )
    finally:
        connection.close()

    with pytest.raises(FactIntegrityError, match="domain contract"):
        asyncio.run(repository.list_as_of(FactQuery(decision_time=_BASE_TIME)))

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            """
            UPDATE source_facts
            SET fact_type = ?, record_json = ?, content_sha256 = ?
            WHERE fact_id = ?
            """,
            [
                "news",
                original_json,
                original_fingerprint,
                str(record.fact_id),
            ],
        )
    finally:
        connection.close()

    with pytest.raises(FactIntegrityError, match="index columns"):
        asyncio.run(repository.list_as_of(FactQuery(decision_time=_BASE_TIME)))

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            "UPDATE source_facts SET fact_type = ? WHERE fact_id = ?",
            [original_type, str(record.fact_id)],
        )
        batch_row = connection.execute(
            """
            SELECT parquet_relative_path, parquet_sha256, record_count
            FROM fact_batches WHERE batch_id = ?
            """,
            [str(receipt.batch_id)],
        ).fetchone()
        assert batch_row is not None
        original_path, original_sha256, original_count = batch_row
        connection.execute(
            "UPDATE fact_batches SET parquet_relative_path = ? WHERE batch_id = ?",
            ["../escape.parquet", str(receipt.batch_id)],
        )
    finally:
        connection.close()

    with pytest.raises(FactIntegrityError, match="unsafe or mismatched"):
        asyncio.run(repository.get_batch_receipt(receipt.batch_id))

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            """
            UPDATE fact_batches
            SET parquet_relative_path = ?, parquet_sha256 = ?, record_count = ?
            WHERE batch_id = ?
            """,
            [original_path, "0" * 64, original_count, str(receipt.batch_id)],
        )
    finally:
        connection.close()

    with pytest.raises(FactIntegrityError, match="SHA-256 audit"):
        asyncio.run(repository.get_batch_receipt(receipt.batch_id))

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            """
            UPDATE fact_batches SET parquet_sha256 = ?, record_count = ?
            WHERE batch_id = ?
            """,
            [original_sha256, original_count + 1, str(receipt.batch_id)],
        )
    finally:
        connection.close()

    with pytest.raises(FactIntegrityError, match="row count"):
        asyncio.run(repository.get_batch_receipt(receipt.batch_id))

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            "UPDATE fact_batches SET record_count = ? WHERE batch_id = ?",
            [original_count, str(receipt.batch_id)],
        )
    finally:
        connection.close()

    receipt.parquet_path.write_bytes(b"tampered parquet")
    with pytest.raises(FactIntegrityError, match="SHA-256 audit"):
        asyncio.run(repository.get_batch_receipt(receipt.batch_id))


def test_fact_repository_rejects_bad_schema_state_and_unsafe_paths(tmp_path: Path) -> None:
    uninitialized, database_path, parquet_root = _repository(tmp_path / "validation")
    query = FactQuery(decision_time=_BASE_TIME)

    with pytest.raises(RuntimeError, match="must be initialized"):
        asyncio.run(uninitialized.list_as_of(query))
    with pytest.raises(RuntimeError, match="must be initialized"):
        asyncio.run(uninitialized.get_batch_receipt(UUID(int=1)))
    with pytest.raises(RuntimeError, match="must be initialized"):
        asyncio.run(uninitialized.add_batch((_record(30, "news", _BASE_TIME),)))

    asyncio.run(uninitialized.initialize())
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            "UPDATE warehouse_metadata SET metadata_value = '999' WHERE metadata_key = 'schema_version'"
        )
    finally:
        connection.close()

    incompatible = DuckDBFactRepository(database_path, parquet_root)
    with pytest.raises(FactIntegrityError, match="unsupported.*999"):
        asyncio.run(incompatible.initialize())

    with pytest.raises(ValueError, match="database_path must be absolute"):
        DuckDBFactRepository(Path("warehouse.duckdb"), parquet_root)
    with pytest.raises(ValueError, match="parquet_root must be absolute"):
        DuckDBFactRepository(database_path, Path("parquet"))

    regular_file = tmp_path / "not-a-directory"
    regular_file.write_text("fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="existing non-symlink directory"):
        DuckDBFactRepository(database_path, regular_file)


def test_content_addressed_raw_store_is_idempotent_and_audited(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    root.mkdir()
    store = ContentAddressedRawStore(root)
    content = b'{"symbol":"MOCK","kind":"news"}'

    async def scenario() -> object:
        first = await store.put(content, suffix=".json")
        second = await store.put(content, suffix=".json")
        assert first == second
        assert first.sha256 == _sha256(content)
        assert first.byte_count == len(content)
        assert first.path.is_relative_to(root)
        assert await store.get(first.sha256, suffix=".json") == content
        assert await store.inspect(first.sha256, suffix=".json") == first
        return first

    raw_object = asyncio.run(scenario())
    assert hasattr(raw_object, "path")
    raw_object.path.write_bytes(b"tampered")

    with pytest.raises(RawStoreIntegrityError, match="does not match"):
        asyncio.run(store.get(raw_object.sha256, suffix=".json"))
    with pytest.raises(RawStoreIntegrityError, match="does not match"):
        asyncio.run(store.put(content, suffix=".json"))


def test_content_addressed_raw_store_rejects_unsafe_inputs(tmp_path: Path) -> None:
    root = tmp_path / "raw-validation"
    root.mkdir()
    store = ContentAddressedRawStore(root)

    with pytest.raises(TypeError, match="must be bytes"):
        asyncio.run(store.put("text"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="suffix"):
        asyncio.run(store.put(b"payload", suffix="../json"))
    with pytest.raises(ValueError, match="suffix"):
        asyncio.run(store.get("0" * 64, suffix=".JSON"))
    with pytest.raises(ValueError, match="sha256"):
        asyncio.run(store.get("not-a-digest"))
    with pytest.raises(RawStoreIntegrityError, match="regular non-symlink"):
        asyncio.run(store.get("0" * 64))
    with pytest.raises(ValueError, match="must be absolute"):
        ContentAddressedRawStore(Path("raw"))

    regular_file = tmp_path / "raw-file"
    regular_file.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="existing non-symlink directory"):
        ContentAddressedRawStore(regular_file)
