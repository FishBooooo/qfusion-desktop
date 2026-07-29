"""Audited, path-safe backup and non-overwriting restore for Local Lite data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Self
from uuid import uuid4

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qfusion.storage.migrations import verify_migration_assets

_MANIFEST_PATH = "manifest.json"
_SQLITE_PATH = PurePosixPath("database/app.sqlite3")
_DUCKDB_PATH = PurePosixPath("database/warehouse.duckdb")
_DATABASE_PATHS = {_SQLITE_PATH, _DUCKDB_PATH}
_ARCHIVE_SUFFIX = ".qfbak"
_MANIFEST_LIMIT = 1024 * 1024
_DEFAULT_FILE_LIMIT = 1_000_000
_DEFAULT_BYTE_LIMIT = 100 * 1024 * 1024 * 1024
_COPY_CHUNK_SIZE = 1024 * 1024
_WINDOWS_FORBIDDEN_PATH_CHARACTERS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "AUX",
        "CON",
        "NUL",
        "PRN",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


class BackupError(ValueError):
    """Base error for backup policy and validation failures."""


class BackupConflictError(BackupError):
    """Raised when an operation would overwrite existing data."""


class BackupIntegrityError(BackupError):
    """Raised when source data or an archive fails integrity validation."""


class BackupEntry(BaseModel):
    """One immutable file declared by a backup manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str = Field(min_length=1, max_length=1024)
    byte_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("relative_path")
    @classmethod
    def require_safe_path(cls, value: str) -> str:
        _validate_payload_path(value)
        return value


class BackupManifest(BaseModel):
    """Versioned integrity and storage-schema manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0.0", pattern=r"^1\.0\.0$")
    created_at: datetime
    sqlite_revision: str = Field(min_length=1, max_length=128)
    duckdb_schema_version: str = Field(min_length=1, max_length=128)
    entries: tuple[BackupEntry, ...]

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_canonical_entries(self) -> Self:
        paths = tuple(entry.relative_path for entry in self.entries)
        if len(paths) != len(set(paths)):
            raise ValueError("backup entries must use unique paths")
        if len(paths) != len({path.casefold() for path in paths}):
            raise ValueError("backup entries must be unique on case-insensitive filesystems")
        if paths != tuple(sorted(paths)):
            raise ValueError("backup entries must be sorted by path")
        if {PurePosixPath(path) for path in paths}.isdisjoint(_DATABASE_PATHS):
            raise ValueError("backup manifest is missing database files")
        if not _DATABASE_PATHS.issubset({PurePosixPath(path) for path in paths}):
            raise ValueError("backup manifest must contain both database files")
        return self


@dataclass(frozen=True, slots=True)
class BackupReceipt:
    """Completed archive identity and its validated manifest."""

    archive_path: Path
    archive_sha256: str
    manifest: BackupManifest


@dataclass(frozen=True, slots=True)
class RestoreReceipt:
    """Completed non-overwriting restore identity."""

    destination_root: Path
    archive_sha256: str
    manifest: BackupManifest


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_directory(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise BackupError(f"{label} must be absolute")
    if not path.is_dir() or path.is_symlink():
        raise BackupError(f"{label} must be an existing non-symlink directory")
    normalized = path.absolute()
    resolved = path.resolve(strict=True)
    if os.path.normcase(str(normalized)) != os.path.normcase(str(resolved)):
        raise BackupError(f"{label} must not traverse a symlink")
    return resolved


def _regular_file(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise BackupError(f"{label} must be absolute")
    if not path.is_file() or path.is_symlink():
        raise BackupError(f"{label} must be a regular non-symlink file")
    normalized = path.absolute()
    resolved = path.resolve(strict=True)
    if os.path.normcase(str(normalized)) != os.path.normcase(str(resolved)):
        raise BackupError(f"{label} must not traverse a symlink")
    return resolved


def _destination_path(path: Path, label: str) -> tuple[Path, Path]:
    if not path.is_absolute():
        raise BackupError(f"{label} must be absolute")
    parent = _existing_directory(path.parent, f"{label} parent")
    normalized = parent / path.name
    if normalized.exists() or normalized.is_symlink():
        raise BackupConflictError(f"{label} already exists")
    return parent, normalized


def _validate_cross_platform_component(value: str) -> None:
    if any(
        ord(character) < 32 or character in _WINDOWS_FORBIDDEN_PATH_CHARACTERS
        for character in value
    ):
        raise BackupIntegrityError("backup path is not portable to Windows")
    if value.endswith((" ", ".")):
        raise BackupIntegrityError("backup path has a Windows-ambiguous suffix")
    basename = value.split(".", maxsplit=1)[0].upper()
    if basename in _WINDOWS_RESERVED_NAMES:
        raise BackupIntegrityError("backup path uses a reserved Windows device name")


def _validate_payload_path(value: str) -> PurePosixPath:
    if "\\" in value or "\x00" in value:
        raise BackupIntegrityError("backup path contains forbidden characters")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        raise BackupIntegrityError("backup path is not canonical and relative")
    for component in path.parts:
        _validate_cross_platform_component(component)
    if path in _DATABASE_PATHS:
        return path
    if len(path.parts) < 2 or path.parts[0] not in {"parquet", "raw"}:
        raise BackupIntegrityError("backup path is outside the Local Lite payload")
    return path


def _walk_regular_files(root: Path, prefix: str) -> tuple[tuple[PurePosixPath, Path], ...]:
    pending = [root]
    collected: list[tuple[PurePosixPath, Path]] = []
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise BackupIntegrityError(f"cannot enumerate backup source: {directory}") from error
        for entry in entries:
            if directory == root and entry.name == ".tmp":
                continue
            if entry.is_symlink():
                raise BackupIntegrityError(f"backup source contains a symlink: {entry.path}")
            path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                relative = path.relative_to(root)
                archive_path = PurePosixPath(prefix, *relative.parts)
                _validate_payload_path(archive_path.as_posix())
                collected.append((archive_path, path))
            else:
                raise BackupIntegrityError(
                    f"backup source contains a non-regular filesystem object: {entry.path}"
                )
    return tuple(sorted(collected, key=lambda item: item[0].as_posix()))


def _sqlite_revision(database_path: Path) -> str:
    connection = sqlite3.connect(str(database_path))
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise BackupIntegrityError("SQLite integrity_check failed")
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError as error:
        raise BackupIntegrityError("SQLite metadata database is invalid") from error
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str) or not row[0]:
        raise BackupIntegrityError("SQLite migration revision is missing")
    return row[0]


def _duckdb_schema_version(database_path: Path) -> str:
    try:
        connection = duckdb.connect(str(database_path), read_only=True)
        try:
            row = connection.execute(
                "SELECT metadata_value FROM warehouse_metadata WHERE metadata_key = ?",
                ["schema_version"],
            ).fetchone()
        finally:
            connection.close()
    except duckdb.Error as error:
        raise BackupIntegrityError("DuckDB warehouse is invalid") from error
    if row is None or not isinstance(row[0], str) or not row[0]:
        raise BackupIntegrityError("DuckDB warehouse schema version is missing")
    return row[0]


def _require_current_schemas(sqlite_revision: str, duckdb_version: str) -> None:
    heads = verify_migration_assets()
    if sqlite_revision not in heads:
        raise BackupIntegrityError(
            f"SQLite revision {sqlite_revision!r} is not the current migration head"
        )
    if duckdb_version != "1":
        raise BackupIntegrityError(
            f"unsupported DuckDB warehouse schema version: {duckdb_version!r}"
        )


def _snapshot_sqlite(source: Path, destination: Path) -> str:
    source_connection = sqlite3.connect(str(source))
    destination_connection = sqlite3.connect(str(destination))
    try:
        source_connection.execute("PRAGMA query_only=ON")
        source_connection.backup(destination_connection)
        destination_connection.commit()
    except sqlite3.DatabaseError as error:
        raise BackupIntegrityError("SQLite online backup failed") from error
    finally:
        destination_connection.close()
        source_connection.close()
    return _sqlite_revision(destination)


def _copy_stable_file(source: Path, destination: Path, label: str) -> None:
    before = source.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise BackupIntegrityError(f"{label} is not a regular file")
    shutil.copyfile(source, destination)
    after = source.stat(follow_symlinks=False)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise BackupIntegrityError(f"{label} changed while the offline backup was running")


def _zip_info(relative_path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(relative_path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100600 << 16
    info.create_system = 3
    return info


def _write_zip_file(
    archive: zipfile.ZipFile,
    relative_path: PurePosixPath,
    source: Path,
) -> BackupEntry:
    before = source.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or source.is_symlink():
        raise BackupIntegrityError(f"backup payload is not a regular file: {source}")

    digest = hashlib.sha256(usedforsecurity=False)
    byte_count = 0
    with (
        source.open("rb") as input_stream,
        archive.open(_zip_info(relative_path.as_posix()), "w") as output_stream,
    ):
        for chunk in iter(lambda: input_stream.read(_COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
            byte_count += len(chunk)
            output_stream.write(chunk)

    after = source.stat(follow_symlinks=False)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise BackupIntegrityError(f"backup payload changed during archive creation: {source}")
    if byte_count != before.st_size:
        raise BackupIntegrityError(f"backup payload size changed during read: {source}")
    return BackupEntry(
        relative_path=relative_path.as_posix(),
        byte_count=byte_count,
        sha256=digest.hexdigest(),
    )


def _canonical_manifest_bytes(manifest: BackupManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _transient_database_paths(database_root: Path) -> tuple[Path, ...]:
    return (
        database_root / "app.sqlite3-wal",
        database_root / "app.sqlite3-shm",
        database_root / "app.sqlite3-journal",
        database_root / "warehouse.duckdb.wal",
    )


class LocalLiteBackupService:
    """Create verified archives and restore only into a new data root."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
        maximum_files: int = _DEFAULT_FILE_LIMIT,
        maximum_bytes: int = _DEFAULT_BYTE_LIMIT,
    ) -> None:
        if maximum_files < 2:
            raise ValueError("maximum_files must allow both database files")
        if maximum_bytes <= 0:
            raise ValueError("maximum_bytes must be positive")
        self._clock = clock
        self._maximum_files = maximum_files
        self._maximum_bytes = maximum_bytes
        self._operation_lock = asyncio.Lock()

    async def create_backup(self, source_root: Path, archive_path: Path) -> BackupReceipt:
        """Create one immutable backup from an offline, quiescent Local Lite root."""

        async with self._operation_lock:
            return await asyncio.to_thread(
                self._create_backup_sync,
                source_root,
                archive_path,
            )

    async def restore_backup(
        self,
        archive_path: Path,
        destination_root: Path,
    ) -> RestoreReceipt:
        """Verify and restore an archive without replacing any existing destination."""

        async with self._operation_lock:
            return await asyncio.to_thread(
                self._restore_backup_sync,
                archive_path,
                destination_root,
            )

    def _create_backup_sync(self, source_root: Path, archive_path: Path) -> BackupReceipt:
        source = _existing_directory(source_root, "source_root")
        database_root = _existing_directory(source / "database", "database root")
        parquet_root = _existing_directory(source / "parquet", "Parquet root")
        raw_root = _existing_directory(source / "raw", "raw root")
        sqlite_source = _regular_file(database_root / "app.sqlite3", "SQLite database")
        duckdb_source = _regular_file(database_root / "warehouse.duckdb", "DuckDB database")

        transients = tuple(
            path
            for path in _transient_database_paths(database_root)
            if path.exists() or path.is_symlink()
        )
        if transients:
            rendered = ", ".join(path.name for path in transients)
            raise BackupIntegrityError(
                f"offline backup refused because transient database files exist: {rendered}"
            )

        if archive_path.suffix.lower() != _ARCHIVE_SUFFIX:
            raise BackupError(f"archive_path must use the {_ARCHIVE_SUFFIX} suffix")
        archive_parent, final_archive = _destination_path(archive_path, "archive_path")
        staging = archive_parent / f".{archive_path.name}.{uuid4().hex}.staging"
        staging.mkdir(mode=0o700)
        temporary_archive = staging / "archive.tmp"

        try:
            staged_database = staging / "database"
            staged_database.mkdir(mode=0o700)
            sqlite_copy = staged_database / _SQLITE_PATH.name
            duckdb_copy = staged_database / _DUCKDB_PATH.name
            sqlite_revision = _snapshot_sqlite(sqlite_source, sqlite_copy)
            _copy_stable_file(duckdb_source, duckdb_copy, "DuckDB database")
            duckdb_version = _duckdb_schema_version(duckdb_copy)
            _require_current_schemas(sqlite_revision, duckdb_version)

            payloads: list[tuple[PurePosixPath, Path]] = [
                (_SQLITE_PATH, sqlite_copy),
                (_DUCKDB_PATH, duckdb_copy),
            ]
            payloads.extend(_walk_regular_files(parquet_root, "parquet"))
            payloads.extend(_walk_regular_files(raw_root, "raw"))
            payloads.sort(key=lambda item: item[0].as_posix())
            if len(payloads) > self._maximum_files:
                raise BackupIntegrityError("backup source exceeds the file-count limit")

            entries: list[BackupEntry] = []
            total_bytes = 0
            with zipfile.ZipFile(
                temporary_archive,
                mode="x",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
                allowZip64=True,
            ) as archive:
                for relative_path, source_path in payloads:
                    entry = _write_zip_file(archive, relative_path, source_path)
                    entries.append(entry)
                    total_bytes += entry.byte_count
                    if total_bytes > self._maximum_bytes:
                        raise BackupIntegrityError("backup source exceeds the byte limit")

                created_at = self._clock()
                if created_at.tzinfo is None or created_at.utcoffset() is None:
                    raise BackupError("backup clock must return a timezone-aware timestamp")
                manifest = BackupManifest(
                    created_at=created_at,
                    sqlite_revision=sqlite_revision,
                    duckdb_schema_version=duckdb_version,
                    entries=tuple(entries),
                )
                archive.writestr(
                    _zip_info(_MANIFEST_PATH),
                    _canonical_manifest_bytes(manifest),
                )

            # Windows requires a writable descriptor for _commit(), which backs
            # os.fsync(); reopen the already closed ZIP without modifying it.
            with temporary_archive.open("r+b") as stream:
                os.fsync(stream.fileno())
            temporary_archive.replace(final_archive)
            archive_sha256 = _sha256(final_archive)
            return BackupReceipt(
                archive_path=final_archive,
                archive_sha256=archive_sha256,
                manifest=manifest,
            )
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _restore_backup_sync(
        self,
        archive_path: Path,
        destination_root: Path,
    ) -> RestoreReceipt:
        archive_file = _regular_file(archive_path, "archive_path")
        if archive_file.suffix.lower() != _ARCHIVE_SUFFIX:
            raise BackupError(f"archive_path must use the {_ARCHIVE_SUFFIX} suffix")
        destination_parent, destination = _destination_path(
            destination_root,
            "destination_root",
        )
        staging = destination_parent / f".{destination.name}.{uuid4().hex}.restore"
        staging.mkdir(mode=0o700)
        archive_sha256 = _sha256(archive_file)

        try:
            manifest = self._extract_verified_archive(archive_file, staging)
            sqlite_revision = _sqlite_revision(staging.joinpath(*_SQLITE_PATH.parts))
            duckdb_version = _duckdb_schema_version(staging.joinpath(*_DUCKDB_PATH.parts))
            if (
                sqlite_revision != manifest.sqlite_revision
                or duckdb_version != manifest.duckdb_schema_version
            ):
                raise BackupIntegrityError("restored database schemas differ from the manifest")
            _require_current_schemas(sqlite_revision, duckdb_version)
            for directory_name in ("database", "parquet", "raw"):
                (staging / directory_name).mkdir(mode=0o700, exist_ok=True)
            staging.replace(destination)
            return RestoreReceipt(
                destination_root=destination,
                archive_sha256=archive_sha256,
                manifest=manifest,
            )
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _extract_verified_archive(self, archive_path: Path, staging: Path) -> BackupManifest:
        try:
            with zipfile.ZipFile(archive_path, mode="r") as archive:
                infos = archive.infolist()
                names = tuple(info.filename for info in infos)
                if len(names) != len(set(names)):
                    raise BackupIntegrityError("backup archive contains duplicate paths")
                info_by_name = {info.filename: info for info in infos}
                manifest_info = info_by_name.get(_MANIFEST_PATH)
                if manifest_info is None or manifest_info.file_size > _MANIFEST_LIMIT:
                    raise BackupIntegrityError("backup manifest is missing or too large")
                self._validate_zip_info(manifest_info, allow_manifest=True)
                manifest = BackupManifest.model_validate_json(archive.read(manifest_info))

                expected_names = {
                    _MANIFEST_PATH,
                    *(entry.relative_path for entry in manifest.entries),
                }
                if set(names) != expected_names:
                    raise BackupIntegrityError(
                        "backup archive entries do not exactly match the manifest"
                    )
                if len(manifest.entries) > self._maximum_files:
                    raise BackupIntegrityError("backup archive exceeds the file-count limit")
                total_bytes = sum(entry.byte_count for entry in manifest.entries)
                if total_bytes > self._maximum_bytes:
                    raise BackupIntegrityError("backup archive exceeds the byte limit")

                for entry in manifest.entries:
                    info = info_by_name[entry.relative_path]
                    self._validate_zip_info(info, allow_manifest=False)
                    if info.file_size != entry.byte_count:
                        raise BackupIntegrityError(
                            f"archive size differs from manifest: {entry.relative_path}"
                        )
                    self._extract_entry(archive, info, entry, staging)
                return manifest
        except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError) as error:
            raise BackupIntegrityError("backup archive is not a valid ZIP container") from error
        except ValueError as error:
            if isinstance(error, BackupError):
                raise
            raise BackupIntegrityError("backup manifest violates its contract") from error

    @staticmethod
    def _validate_zip_info(info: zipfile.ZipInfo, *, allow_manifest: bool) -> None:
        expected = _MANIFEST_PATH if allow_manifest else info.filename
        if info.filename != expected or info.is_dir():
            raise BackupIntegrityError("backup archive contains an invalid entry")
        if info.flag_bits & 0x1:
            raise BackupIntegrityError("encrypted ZIP entries are not supported by M1")
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        if file_type == stat.S_IFLNK:
            raise BackupIntegrityError("backup archive contains a symbolic link")
        if file_type not in {0, stat.S_IFREG}:
            raise BackupIntegrityError("backup archive contains a non-regular entry")
        if not allow_manifest:
            _validate_payload_path(info.filename)

    @staticmethod
    def _extract_entry(
        archive: zipfile.ZipFile,
        info: zipfile.ZipInfo,
        entry: BackupEntry,
        staging: Path,
    ) -> None:
        relative = _validate_payload_path(entry.relative_path)
        destination = staging.joinpath(*relative.parts)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        digest = hashlib.sha256(usedforsecurity=False)
        byte_count = 0
        with (
            archive.open(info, mode="r") as input_stream,
            destination.open("xb") as output_stream,
        ):
            for chunk in iter(lambda: input_stream.read(_COPY_CHUNK_SIZE), b""):
                digest.update(chunk)
                byte_count += len(chunk)
                if byte_count > entry.byte_count:
                    raise BackupIntegrityError(
                        f"archive entry exceeds its declared size: {entry.relative_path}"
                    )
                output_stream.write(chunk)
        if byte_count != entry.byte_count or digest.hexdigest() != entry.sha256:
            raise BackupIntegrityError(
                f"archive entry failed its SHA-256 audit: {entry.relative_path}"
            )
