"""Content-addressed storage for immutable provider payloads and documents."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from qfusion.storage.facts import _resolve_existing_directory

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SUFFIX_PATTERN = re.compile(r"^\.[a-z0-9]{1,10}$")


class RawStoreIntegrityError(ValueError):
    """Raised when a raw object is missing, unsafe, or fails its content hash."""


@dataclass(frozen=True, slots=True)
class RawObject:
    """Verified reference to one immutable content-addressed raw object."""

    sha256: str
    byte_count: int
    path: Path
    suffix: str


def _content_sha256(content: bytes) -> str:
    return hashlib.sha256(content, usedforsecurity=False).hexdigest()


def _validate_digest(value: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("sha256 must be a lowercase 64-character hexadecimal digest")
    return value


def _validate_suffix(value: str) -> str:
    if _SUFFIX_PATTERN.fullmatch(value) is None:
        raise ValueError("suffix must be a lowercase alphanumeric file extension")
    return value


def _object_relative_path(digest: str, suffix: str) -> PurePosixPath:
    return PurePosixPath("objects") / digest[:2] / digest[2:4] / f"{digest}{suffix}"


def _resolve_regular_raw_object(root: Path, relative: PurePosixPath) -> Path:
    candidate = root.joinpath(*relative.parts)
    if not candidate.is_file() or candidate.is_symlink():
        raise RawStoreIntegrityError("raw object must be a regular non-symlink file")
    normalized = Path(os.path.abspath(candidate))
    resolved = candidate.resolve(strict=True)
    if (
        os.path.normcase(str(normalized)) != os.path.normcase(str(resolved))
        or not resolved.is_relative_to(root)
    ):
        raise RawStoreIntegrityError("raw object escaped its storage root")
    return resolved


class ContentAddressedRawStore:
    """Persist raw bytes under a deterministic SHA-256 path within one root."""

    def __init__(self, root: Path) -> None:
        self._root = _resolve_existing_directory(root, "raw store root")
        object_root = self._root / "objects"
        object_root.mkdir(mode=0o700, exist_ok=True)
        self._object_root = _resolve_existing_directory(object_root, "raw object directory")
        temporary_root = self._root / ".tmp"
        temporary_root.mkdir(mode=0o700, exist_ok=True)
        self._temporary_root = _resolve_existing_directory(
            temporary_root,
            "raw store temporary directory",
        )

    async def put(self, content: bytes, *, suffix: str = ".bin") -> RawObject:
        """Write or audit one object without replacing an existing hash path."""

        if not isinstance(content, bytes):
            raise TypeError("raw store content must be bytes")
        selected_suffix = _validate_suffix(suffix)
        return await asyncio.to_thread(self._put_sync, content, selected_suffix)

    async def get(self, sha256: str, *, suffix: str = ".bin") -> bytes:
        """Read one object only after validating its path and content hash."""

        digest = _validate_digest(sha256)
        selected_suffix = _validate_suffix(suffix)
        return await asyncio.to_thread(self._get_sync, digest, selected_suffix)

    async def inspect(self, sha256: str, *, suffix: str = ".bin") -> RawObject:
        """Return a verified immutable object reference without returning its bytes."""

        digest = _validate_digest(sha256)
        selected_suffix = _validate_suffix(suffix)
        return await asyncio.to_thread(self._inspect_sync, digest, selected_suffix)

    def _put_sync(self, content: bytes, suffix: str) -> RawObject:
        digest = _content_sha256(content)
        relative = _object_relative_path(digest, suffix)
        parent = self._object_root / digest[:2] / digest[2:4]
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        resolved_parent = _resolve_existing_directory(parent, "raw object shard directory")
        target = resolved_parent / relative.name

        if target.exists():
            return self._inspect_sync(digest, suffix)

        temporary = self._temporary_root / f"{uuid4()}.part"
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.is_symlink() or not temporary.is_file():
                raise RawStoreIntegrityError("raw store temporary object is not a regular file")
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return self._inspect_sync(digest, suffix)

    def _get_sync(self, digest: str, suffix: str) -> bytes:
        raw_object = self._inspect_sync(digest, suffix)
        content = raw_object.path.read_bytes()
        if _content_sha256(content) != digest:
            raise RawStoreIntegrityError("raw object changed while it was being read")
        return content

    def _inspect_sync(self, digest: str, suffix: str) -> RawObject:
        relative = _object_relative_path(digest, suffix)
        path = _resolve_regular_raw_object(self._root, relative)
        content = path.read_bytes()
        if _content_sha256(content) != digest:
            raise RawStoreIntegrityError("raw object SHA-256 does not match its path")
        return RawObject(
            sha256=digest,
            byte_count=len(content),
            path=path,
            suffix=suffix,
        )
