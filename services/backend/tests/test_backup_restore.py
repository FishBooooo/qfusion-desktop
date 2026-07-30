"""Local Lite backup manifest, integrity, and non-overwriting restore tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import stat
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import duckdb
import pytest

from qfusion.domain import (
    AnalysisSnapshot,
    DataSourceRecord,
    FactQuery,
    Market,
    QualityFlag,
    RequestedHorizon,
    TargetType,
)
from qfusion.storage import (
    BackupConflictError,
    BackupError,
    BackupIntegrityError,
    ContentAddressedRawStore,
    DuckDBFactRepository,
    FactWriteQueue,
    LocalLiteBackupService,
    SqlAlchemySnapshotRepository,
    create_session_factory,
    create_sqlite_engine,
    upgrade_database,
)

_DECISION_TIME = datetime(2026, 7, 30, 15, 0, tzinfo=UTC)
_INSTRUMENT_ID = UUID("70000000-0000-4000-8000-000000000001")
_FACT_ID = UUID("70000000-0000-4000-8000-000000000002")
_SNAPSHOT_ID = UUID("70000000-0000-4000-8000-000000000003")
_RAW_CONTENT = b'{"kind":"m1e-synthetic-news","symbol":"MOCK"}'


def _record() -> DataSourceRecord:
    return DataSourceRecord(
        fact_id=_FACT_ID,
        instrument_id=_INSTRUMENT_ID,
        fact_type="market.bar.daily",
        source="M1-E Synthetic Mock",
        source_record_id="m1e-daily-1",
        source_quality_level="synthetic-contract-only",
        venue_scope="US synthetic fixture",
        license_scope="repository test fixture",
        provider_version="m1e.mock.1",
        dataset_version="m1e-bars-v1",
        event_time=_DECISION_TIME - timedelta(minutes=5),
        published_at=_DECISION_TIME - timedelta(minutes=4),
        available_at=_DECISION_TIME - timedelta(minutes=3),
        received_at=_DECISION_TIME - timedelta(minutes=2),
        ingested_at=_DECISION_TIME - timedelta(minutes=1),
        revision_id="original",
        quality_flag=QualityFlag.SYNTHETIC_MOCK,
        raw_payload_hash=hashlib.sha256(
            _RAW_CONTENT,
            usedforsecurity=False,
        ).hexdigest(),
        is_adjusted=True,
        adjustment_type="split-and-dividend",
        payload={"close": 101.25, "mock": True},
    )


def _snapshot(record: DataSourceRecord) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        snapshot_id=_SNAPSHOT_ID,
        target_type=TargetType.STOCK,
        target_id=_INSTRUMENT_ID,
        market=Market.US,
        requested_horizon=RequestedHorizon.FIVE_DAY,
        decision_time=_DECISION_TIME,
        market_timezone="America/New_York",
        created_at=_DECISION_TIME + timedelta(seconds=1),
        price_as_of=record.event_time,
        provider_versions={record.source: record.provider_version},
        dataset_versions={f"{record.source}::{record.fact_type}": record.dataset_version},
        fact_ids=(record.fact_id,),
        quality_score=0.5,
    )


def _create_source(root: Path) -> tuple[DataSourceRecord, AnalysisSnapshot, UUID, str]:
    database_root = root / "database"
    parquet_root = root / "parquet"
    raw_root = root / "raw"
    database_root.mkdir(parents=True)
    parquet_root.mkdir()
    raw_root.mkdir()

    metadata_engine = create_sqlite_engine(database_root / "app.sqlite3")
    upgrade_database(metadata_engine)
    snapshot_repository = SqlAlchemySnapshotRepository(
        create_session_factory(metadata_engine)
    )
    fact_repository = DuckDBFactRepository(
        database_root / "warehouse.duckdb",
        parquet_root,
    )
    raw_store = ContentAddressedRawStore(raw_root)
    record = _record()
    snapshot = _snapshot(record)

    async def scenario() -> tuple[UUID, str]:
        await fact_repository.initialize()
        async with FactWriteQueue(fact_repository) as writer:
            receipt = await writer.submit((record,))
        await snapshot_repository.add(snapshot)
        raw_object = await raw_store.put(_RAW_CONTENT, suffix=".json")
        return receipt.batch_id, raw_object.sha256

    try:
        batch_id, raw_sha256 = asyncio.run(scenario())
    finally:
        metadata_engine.dispose()

    (parquet_root / ".tmp" / "excluded.tmp").write_bytes(b"transient")
    (root / "not-part-of-local-lite.log").write_text("excluded", encoding="utf-8")
    return record, snapshot, batch_id, raw_sha256


def _rewrite_archive(
    source: Path,
    destination: Path,
    transform: Callable[[zipfile.ZipInfo, bytes], tuple[zipfile.ZipInfo, bytes]],
) -> None:
    with (
        zipfile.ZipFile(source, "r") as input_archive,
        zipfile.ZipFile(destination, "x") as output_archive,
    ):
        for original_info in input_archive.infolist():
            info = zipfile.ZipInfo(original_info.filename, original_info.date_time)
            info.compress_type = original_info.compress_type
            info.external_attr = original_info.external_attr
            info.create_system = original_info.create_system
            content = input_archive.read(original_info)
            new_info, new_content = transform(info, content)
            output_archive.writestr(new_info, new_content)


def test_backup_restore_round_trip_across_all_local_lite_stores(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    record, snapshot, batch_id, raw_sha256 = _create_source(source)
    archive = tmp_path / "qfusion-backup.qfbak"
    restored = tmp_path / "restored"
    service = LocalLiteBackupService(clock=lambda: _DECISION_TIME + timedelta(hours=1))

    async def scenario() -> tuple[object, object]:
        backup = await service.create_backup(source, archive)
        restore = await service.restore_backup(archive, restored)
        return backup, restore

    backup, restore = asyncio.run(scenario())

    assert backup.archive_path == archive
    assert backup.archive_sha256 == restore.archive_sha256
    assert backup.manifest == restore.manifest
    manifest_paths = tuple(entry.relative_path for entry in backup.manifest.entries)
    assert manifest_paths == tuple(sorted(manifest_paths))
    assert "database/app.sqlite3" in manifest_paths
    assert "database/warehouse.duckdb" in manifest_paths
    assert any(path.startswith("parquet/batches/") for path in manifest_paths)
    assert any(path.startswith("raw/objects/") for path in manifest_paths)
    assert not any("/.tmp/" in f"/{path}/" for path in manifest_paths)
    assert "not-part-of-local-lite.log" not in manifest_paths

    metadata_engine = create_sqlite_engine(restored / "database" / "app.sqlite3")
    snapshot_repository = SqlAlchemySnapshotRepository(
        create_session_factory(metadata_engine)
    )
    fact_repository = DuckDBFactRepository(
        restored / "database" / "warehouse.duckdb",
        restored / "parquet",
    )
    raw_store = ContentAddressedRawStore(restored / "raw")

    async def verify_restored() -> None:
        await fact_repository.initialize()
        assert await snapshot_repository.get(snapshot.snapshot_id) == snapshot
        assert await fact_repository.list_as_of(
            FactQuery(
                decision_time=_DECISION_TIME,
                instrument_ids=(_INSTRUMENT_ID,),
                fact_types=("market.bar.daily",),
            )
        ) == (record,)
        receipt = await fact_repository.get_batch_receipt(batch_id)
        assert receipt is not None
        assert receipt.parquet_path.is_relative_to(restored / "parquet")
        assert await raw_store.get(raw_sha256, suffix=".json") == _RAW_CONTENT

    try:
        asyncio.run(verify_restored())
    finally:
        metadata_engine.dispose()


def test_restore_rejects_hash_tampering_and_corrupt_containers(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _create_source(source)
    archive = tmp_path / "valid.qfbak"
    service = LocalLiteBackupService()
    asyncio.run(service.create_backup(source, archive))

    tampered = tmp_path / "tampered.qfbak"

    def change_raw_payload(
        info: zipfile.ZipInfo,
        content: bytes,
    ) -> tuple[zipfile.ZipInfo, bytes]:
        if info.filename.startswith("raw/objects/"):
            return info, b"X" + content[1:]
        return info, content

    _rewrite_archive(archive, tampered, change_raw_payload)
    with pytest.raises(BackupIntegrityError, match="SHA-256"):
        asyncio.run(service.restore_backup(tampered, tmp_path / "tampered-restore"))
    assert not (tmp_path / "tampered-restore").exists()

    corrupt = tmp_path / "corrupt.qfbak"
    corrupt.write_bytes(b"not a zip archive")
    with pytest.raises(BackupIntegrityError, match="valid ZIP"):
        asyncio.run(service.restore_backup(corrupt, tmp_path / "corrupt-restore"))


def test_restore_rejects_traversal_extra_entries_and_zip_symlinks(tmp_path: Path) -> None:
    service = LocalLiteBackupService()
    traversal = tmp_path / "traversal.qfbak"
    invalid_manifest = {
        "schema_version": "1.0.0",
        "created_at": _DECISION_TIME.isoformat(),
        "sqlite_revision": "0002_m2b_instruments",
        "duckdb_schema_version": "1",
        "entries": [
            {"relative_path": "../escape", "byte_count": 1, "sha256": "0" * 64},
            {
                "relative_path": "database/app.sqlite3",
                "byte_count": 1,
                "sha256": "0" * 64,
            },
            {
                "relative_path": "database/warehouse.duckdb",
                "byte_count": 1,
                "sha256": "0" * 64,
            },
        ],
    }
    with zipfile.ZipFile(traversal, "x") as archive:
        archive.writestr("manifest.json", json.dumps(invalid_manifest))
    with pytest.raises(BackupIntegrityError, match="manifest"):
        asyncio.run(service.restore_backup(traversal, tmp_path / "traversal-restore"))
    assert not (tmp_path / "escape").exists()

    source = tmp_path / "source"
    source.mkdir()
    _create_source(source)
    valid = tmp_path / "valid.qfbak"
    asyncio.run(service.create_backup(source, valid))

    extra = tmp_path / "extra.qfbak"

    def retain(
        info: zipfile.ZipInfo,
        content: bytes,
    ) -> tuple[zipfile.ZipInfo, bytes]:
        return info, content

    _rewrite_archive(valid, extra, retain)
    with zipfile.ZipFile(extra, "a") as archive:
        archive.writestr("raw/unlisted.bin", b"extra")
    with pytest.raises(BackupIntegrityError, match="exactly match"):
        asyncio.run(service.restore_backup(extra, tmp_path / "extra-restore"))

    symlink_archive = tmp_path / "symlink.qfbak"

    def mark_database_as_symlink(
        info: zipfile.ZipInfo,
        content: bytes,
    ) -> tuple[zipfile.ZipInfo, bytes]:
        if info.filename == "database/app.sqlite3":
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        return info, content

    _rewrite_archive(valid, symlink_archive, mark_database_as_symlink)
    with pytest.raises(BackupIntegrityError, match="symbolic link"):
        asyncio.run(service.restore_backup(symlink_archive, tmp_path / "link-restore"))


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "raw/CON",
        "raw/con.txt",
        "raw/report.txt:secret",
        "raw/trailing.",
        "raw/question?.json",
    ],
)
def test_restore_rejects_windows_unsafe_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    manifest_entries = sorted(
        [
            {
                "relative_path": "database/app.sqlite3",
                "byte_count": 1,
                "sha256": "0" * 64,
            },
            {
                "relative_path": "database/warehouse.duckdb",
                "byte_count": 1,
                "sha256": "0" * 64,
            },
            {
                "relative_path": unsafe_path,
                "byte_count": 1,
                "sha256": "0" * 64,
            },
        ],
        key=lambda entry: str(entry["relative_path"]),
    )
    archive_path = tmp_path / "windows-unsafe.qfbak"
    with zipfile.ZipFile(archive_path, "x") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "created_at": _DECISION_TIME.isoformat(),
                    "sqlite_revision": "0002_m2b_instruments",
                    "duckdb_schema_version": "1",
                    "entries": manifest_entries,
                }
            ),
        )
    with pytest.raises(BackupIntegrityError, match="manifest"):
        asyncio.run(
            LocalLiteBackupService().restore_backup(
                archive_path,
                tmp_path / "unsafe-restore",
            )
        )


def test_restore_rejects_case_collisions_and_non_regular_entries(
    tmp_path: Path,
) -> None:
    case_collision = tmp_path / "case-collision.qfbak"
    entries = [
        {
            "relative_path": path,
            "byte_count": 1,
            "sha256": "0" * 64,
        }
        for path in (
            "database/app.sqlite3",
            "database/warehouse.duckdb",
            "raw/A",
            "raw/a",
        )
    ]
    with zipfile.ZipFile(case_collision, "x") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "created_at": _DECISION_TIME.isoformat(),
                    "sqlite_revision": "0002_m2b_instruments",
                    "duckdb_schema_version": "1",
                    "entries": entries,
                }
            ),
        )
    with pytest.raises(BackupIntegrityError, match="manifest"):
        asyncio.run(
            LocalLiteBackupService().restore_backup(
                case_collision,
                tmp_path / "collision-restore",
            )
        )

    source = tmp_path / "source-for-special-entry"
    source.mkdir()
    _create_source(source)
    valid = tmp_path / "valid-for-special-entry.qfbak"
    service = LocalLiteBackupService()
    asyncio.run(service.create_backup(source, valid))
    special = tmp_path / "special-entry.qfbak"

    def mark_database_as_fifo(
        info: zipfile.ZipInfo,
        content: bytes,
    ) -> tuple[zipfile.ZipInfo, bytes]:
        if info.filename == "database/app.sqlite3":
            info.external_attr = (stat.S_IFIFO | 0o600) << 16
        return info, content

    _rewrite_archive(valid, special, mark_database_as_fifo)
    with pytest.raises(BackupIntegrityError, match="non-regular"):
        asyncio.run(
            service.restore_backup(special, tmp_path / "special-restore")
        )


def test_backup_refuses_live_transients_symlinks_and_size_limits(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _create_source(source)
    service = LocalLiteBackupService()

    transient = source / "database" / "warehouse.duckdb.wal"
    transient.write_bytes(b"active writer sentinel")
    with pytest.raises(BackupIntegrityError, match="transient database files"):
        asyncio.run(service.create_backup(source, tmp_path / "transient.qfbak"))
    transient.unlink()

    link = source / "raw" / "internal-link"
    try:
        link.symlink_to(source / "raw" / "objects", target_is_directory=True)
    except (NotImplementedError, OSError):
        pass
    else:
        with pytest.raises(BackupIntegrityError, match="contains a symlink"):
            asyncio.run(service.create_backup(source, tmp_path / "symlink-source.qfbak"))
        link.unlink()

    with pytest.raises(BackupIntegrityError, match="file-count"):
        asyncio.run(
            LocalLiteBackupService(maximum_files=2).create_backup(
                source,
                tmp_path / "too-many.qfbak",
            )
        )
    with pytest.raises(BackupIntegrityError, match="byte limit"):
        asyncio.run(
            LocalLiteBackupService(maximum_bytes=2).create_backup(
                source,
                tmp_path / "too-large.qfbak",
            )
        )


def test_backup_and_restore_never_overwrite_existing_paths(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _create_source(source)
    archive = tmp_path / "backup.qfbak"
    service = LocalLiteBackupService()
    asyncio.run(service.create_backup(source, archive))

    with pytest.raises(BackupConflictError, match="already exists"):
        asyncio.run(service.create_backup(source, archive))

    destination = tmp_path / "existing-destination"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(BackupConflictError, match="already exists"):
        asyncio.run(service.restore_backup(archive, destination))
    assert sentinel.read_text(encoding="utf-8") == "preserve"

    with pytest.raises(BackupError, match=r"\.qfbak"):
        asyncio.run(service.create_backup(source, tmp_path / "wrong.zip"))
    with pytest.raises(BackupError, match="absolute"):
        asyncio.run(service.create_backup(Path("relative"), tmp_path / "unused.qfbak"))

    naive_clock = LocalLiteBackupService(clock=lambda: datetime(2026, 7, 30, 16, 0))
    with pytest.raises(BackupError, match="timezone-aware"):
        asyncio.run(naive_clock.create_backup(source, tmp_path / "naive.qfbak"))
    assert not (tmp_path / "naive.qfbak").exists()


def test_backup_rejects_unknown_database_schema_versions(tmp_path: Path) -> None:
    duckdb_source = tmp_path / "duckdb-source"
    duckdb_source.mkdir()
    _create_source(duckdb_source)
    connection = duckdb.connect(
        str(duckdb_source / "database" / "warehouse.duckdb")
    )
    try:
        connection.execute(
            "UPDATE warehouse_metadata SET metadata_value = '999' "
            "WHERE metadata_key = 'schema_version'"
        )
    finally:
        connection.close()
    with pytest.raises(BackupIntegrityError, match="unsupported DuckDB"):
        asyncio.run(
            LocalLiteBackupService().create_backup(
                duckdb_source,
                tmp_path / "unsupported-duckdb.qfbak",
            )
        )

    sqlite_source = tmp_path / "sqlite-source"
    sqlite_source.mkdir()
    _create_source(sqlite_source)
    connection_sqlite = sqlite3.connect(
        str(sqlite_source / "database" / "app.sqlite3")
    )
    try:
        connection_sqlite.execute("UPDATE alembic_version SET version_num = 'unknown'")
        connection_sqlite.commit()
    finally:
        connection_sqlite.close()
    with pytest.raises(BackupIntegrityError, match="current migration head"):
        asyncio.run(
            LocalLiteBackupService().create_backup(
                sqlite_source,
                tmp_path / "unsupported-sqlite.qfbak",
            )
        )
