"""Atomic local implementation of the shared ArtifactPort."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import stat
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO

from everweb.domain import ArtifactRef, ArtifactWrite
from everweb.domain.sensitive import contains_sensitive_content
from everweb.ports import ClockPort

_platform_lock: Any = importlib.import_module(
    "msvcrt" if os.name == "nt" else "fcntl"
)

ALLOWED_ARTIFACT_ROOTS = frozenset(
    {
        "diagnostics",
        "documents",
        "model_receipts",
        "network",
        "screenshots",
    }
)
class ArtifactStoreError(Exception):
    """Base error for immutable artifact storage."""


class ArtifactValidationError(ArtifactStoreError):
    """Artifact metadata, content, or path is invalid."""


class SensitiveArtifactError(ArtifactStoreError):
    """Shared artifact content contains a sensitive field."""


class ArtifactConflictError(ArtifactStoreError):
    """An immutable artifact identity or path already exists."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Stored bytes do not match their ArtifactRef."""


def _validate_portable_segment(value: str, *, field_name: str) -> None:
    windows_value = PureWindowsPath(value)
    invalid_character = any(
        character in '<>:"/\\|?*' or ord(character) < 32 for character in value
    )
    if (
        not value
        or value in {".", ".."}
        or invalid_character
        or value.endswith((".", " "))
        or windows_value.is_absolute()
        or bool(windows_value.drive)
        or len(windows_value.parts) != 1
        or windows_value.is_reserved()
    ):
        raise ArtifactValidationError(
            f"{field_name} must be one portable path segment"
        )


def _artifact_parts(relative_path: str) -> tuple[str, ...]:
    if "\\" in relative_path:
        raise ArtifactValidationError("artifact path must use POSIX separators")
    path = PurePosixPath(relative_path)
    parts = path.parts
    if (
        not relative_path
        or path.is_absolute()
        or path.as_posix() != relative_path
        or len(parts) < 2
        or parts[0] not in ALLOWED_ARTIFACT_ROOTS
    ):
        raise ArtifactValidationError("artifact path is outside allowed directories")
    for part in parts:
        _validate_portable_segment(part, field_name="artifact path segment")
    return parts


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArtifactValidationError(
            "artifact JSON content must be strict canonical JSON"
        ) from exc


def _reject_sensitive_content(content: bytes) -> None:
    if contains_sensitive_content(content):
        raise SensitiveArtifactError(
            "shared artifact contains a sensitive field"
        )


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


class FilesystemArtifactStore:
    """Store immutable shared artifacts beneath one execution directory."""

    def __init__(
        self,
        *,
        run_root: Path,
        execution_id: str,
        max_artifact_bytes: int,
        clock: ClockPort,
    ) -> None:
        _validate_portable_segment(execution_id, field_name="execution_id")
        if max_artifact_bytes <= 0:
            raise ValueError("max_artifact_bytes must be positive")

        self.run_directory = run_root / execution_id
        self.run_directory.mkdir(parents=True, exist_ok=True)
        resolved_root = run_root.resolve(strict=True)
        resolved_run_directory = self.run_directory.resolve(strict=True)
        if (
            _is_link_or_junction(self.run_directory)
            or not resolved_run_directory.is_relative_to(resolved_root)
        ):
            raise ArtifactValidationError(
                "execution directory escapes run_root"
            )
        self._resolved_run_directory = resolved_run_directory
        self._max_artifact_bytes = max_artifact_bytes
        self._clock = clock
        self._artifact_ids: set[str] = set()
        self._lock = threading.Lock()
        self._id_directory = self.run_directory / ".artifact_ids"
        self._id_directory.mkdir(exist_ok=True)
        self._lock_path = self._id_directory / ".store.lock"
        self._validate_id_directory()
        with self._exclusive_store_lock():
            self._recover_identity_records()

    def _validate_id_directory(self) -> None:
        resolved_id_directory = self._id_directory.resolve(strict=True)
        if (
            _is_link_or_junction(self._id_directory)
            or not self._id_directory.is_dir()
            or not resolved_id_directory.is_relative_to(
                self._resolved_run_directory
            )
        ):
            raise ArtifactValidationError(
                "artifact identity directory must be a real directory"
            )

    def put_bytes(self, req: ArtifactWrite) -> ArtifactRef:
        if not isinstance(req.content, bytes):
            raise ArtifactValidationError("put_bytes requires bytes content")
        return self._put(req, req.content)

    def put_json(self, req: ArtifactWrite) -> ArtifactRef:
        if isinstance(req.content, bytes):
            raise ArtifactValidationError("put_json requires JSON content")
        return self._put(req, _canonical_json_bytes(req.content))

    def _put(self, req: ArtifactWrite, content: bytes) -> ArtifactRef:
        _validate_portable_segment(req.artifact_id, field_name="artifact_id")
        parts = _artifact_parts(req.relative_path)
        if not req.kind:
            raise ArtifactValidationError("artifact kind must be non-empty")
        if len(content) > self._max_artifact_bytes:
            raise ArtifactValidationError(
                f"artifact is {len(content)} bytes; "
                f"limit is {self._max_artifact_bytes}"
            )
        metadata = "\n".join(
            (
                req.artifact_id,
                req.kind,
                req.relative_path,
                req.mime_type or "",
            )
        ).encode("utf-8")
        _reject_sensitive_content(metadata)
        _reject_sensitive_content(content)
        reference = ArtifactRef(
            artifact_id=req.artifact_id,
            kind=req.kind,
            relative_path=PurePosixPath(*parts).as_posix(),
            sha256=_sha256(content),
            byte_size=len(content),
            mime_type=req.mime_type,
            created_at=self._clock.now(),
            redacted=False,
        )

        parent = self._prepare_parent(parts[:-1])
        target = parent / parts[-1]

        with self._lock, self._exclusive_store_lock():
            self._recover_identity_records()
            if req.artifact_id in self._artifact_ids:
                raise ArtifactConflictError("artifact_id already exists")
            if target.exists():
                raise ArtifactConflictError("artifact path already exists")

            temporary_path: Path | None = None
            published = False
            identity_marker = self._reserve_artifact_id(reference)
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w+b",
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    dir=parent,
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())

                persisted = temporary_path.read_bytes()
                if persisted != content:
                    raise ArtifactIntegrityError(
                        "temporary artifact read-back mismatch"
                    )

                try:
                    os.link(temporary_path, target)
                except FileExistsError as exc:
                    raise ArtifactConflictError(
                        "artifact path already exists"
                    ) from exc
                published = True
                temporary_path.unlink()
                temporary_path = None
                self._fsync_directory(parent)
                self._commit_artifact_id(
                    identity_marker,
                    req.artifact_id,
                )
                self._artifact_ids.add(req.artifact_id)
            except Exception:
                target_removal_durable = True
                if published:
                    target_removal_durable = self._remove_durably(
                        target,
                        parent,
                    )
                if target_removal_durable:
                    self._remove_durably(
                        identity_marker,
                        self._id_directory,
                    )
                    self._remove_durably(
                        self._committed_id_path(req.artifact_id),
                        self._id_directory,
                    )
                raise
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

        return reference

    def _pending_id_path(self, artifact_id: str) -> Path:
        return self._id_directory / f"{artifact_id}.pending"

    def _committed_id_path(self, artifact_id: str) -> Path:
        return self._id_directory / f"{artifact_id}.json"

    def _reserve_artifact_id(self, ref: ArtifactRef) -> Path:
        self._validate_id_directory()
        committed = self._committed_id_path(ref.artifact_id)
        if committed.exists():
            raise ArtifactConflictError("artifact_id already exists")
        marker = self._pending_id_path(ref.artifact_id)
        record = {
            "artifact_id": ref.artifact_id,
            "byte_size": ref.byte_size,
            "relative_path": ref.relative_path,
            "sha256": ref.sha256,
        }
        try:
            with marker.open("xb") as marker_file:
                marker_file.write(_canonical_json_bytes(record))
                marker_file.flush()
                os.fsync(marker_file.fileno())
            self._fsync_directory(self._id_directory)
        except FileExistsError as exc:
            raise ArtifactConflictError("artifact_id already exists") from exc
        except Exception:
            self._remove_durably(marker, self._id_directory)
            raise
        return marker

    def _commit_artifact_id(
        self,
        pending: Path,
        artifact_id: str,
    ) -> None:
        committed = self._committed_id_path(artifact_id)
        if committed.exists():
            raise ArtifactConflictError("artifact_id already exists")
        os.replace(pending, committed)
        self._fsync_directory(self._id_directory)

    def _recover_identity_records(self) -> None:
        for marker in self._id_directory.iterdir():
            if marker == self._lock_path:
                continue
            if not marker.is_file() or _is_link_or_junction(marker):
                raise ArtifactIntegrityError(
                    "artifact identity record is not a regular file"
                )
            if marker.name.endswith(".pending"):
                self._recover_pending_marker(marker)
            elif marker.name.endswith(".json"):
                artifact_id = marker.name[: -len(".json")]
                record = self._read_identity_record(marker, artifact_id)
                self._verify_recorded_artifact(record)
                self._artifact_ids.add(artifact_id)
            else:
                raise ArtifactIntegrityError(
                    "unexpected artifact identity record"
                )

    @contextmanager
    def _exclusive_store_lock(self) -> Iterator[None]:
        if self._lock_path.is_symlink() or self._lock_path.is_junction():
            raise ArtifactValidationError(
                "artifact store lock must not be a link or junction"
            )
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._lock_path, flags, 0o600)
        with os.fdopen(descriptor, "r+b") as lock_file:
            self._validate_open_lock_file(lock_file)
            self._acquire_file_lock(lock_file)
            try:
                yield
            finally:
                self._release_file_lock(lock_file)

    def _validate_open_lock_file(self, lock_file: BinaryIO) -> None:
        descriptor_stat = os.fstat(lock_file.fileno())
        path_stat = self._lock_path.stat(follow_symlinks=False)
        resolved = self._lock_path.resolve(strict=True)
        if (
            not stat.S_ISREG(path_stat.st_mode)
            or descriptor_stat.st_dev != path_stat.st_dev
            or descriptor_stat.st_ino != path_stat.st_ino
            or not resolved.is_relative_to(self._resolved_run_directory)
        ):
            raise ArtifactValidationError(
                "artifact store lock must be a contained regular file"
            )

    @staticmethod
    def _acquire_file_lock(lock_file: BinaryIO) -> None:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            _platform_lock.locking(
                lock_file.fileno(),
                _platform_lock.LK_LOCK,
                1,
            )
        else:
            _platform_lock.flock(
                lock_file.fileno(),
                _platform_lock.LOCK_EX,
            )

    @staticmethod
    def _release_file_lock(lock_file: BinaryIO) -> None:
        if os.name == "nt":
            lock_file.seek(0)
            _platform_lock.locking(
                lock_file.fileno(),
                _platform_lock.LK_UNLCK,
                1,
            )
        else:
            _platform_lock.flock(
                lock_file.fileno(),
                _platform_lock.LOCK_UN,
            )

    def _recover_pending_marker(self, marker: Path) -> None:
        artifact_id = marker.name[: -len(".pending")]
        record = self._read_identity_record(marker, artifact_id)
        target = self._recorded_artifact_path(record)
        if not target.exists():
            marker.unlink()
            self._fsync_directory(self._id_directory)
            return
        self._verify_recorded_artifact(record)
        self._commit_artifact_id(marker, artifact_id)
        self._artifact_ids.add(artifact_id)

    def _read_identity_record(
        self,
        marker: Path,
        artifact_id: str,
    ) -> dict[str, object]:
        try:
            record = json.loads(marker.read_bytes())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ArtifactIntegrityError(
                "invalid artifact identity record"
            ) from exc
        if (
            not isinstance(record, dict)
            or record.get("artifact_id") != artifact_id
            or not isinstance(record.get("relative_path"), str)
            or not isinstance(record.get("sha256"), str)
            or type(record.get("byte_size")) is not int
        ):
            raise ArtifactIntegrityError(
                "invalid artifact identity record"
            )
        return record

    def _recorded_artifact_path(self, record: dict[str, object]) -> Path:
        relative_path = record["relative_path"]
        assert isinstance(relative_path, str)
        parts = _artifact_parts(relative_path)
        path = self.run_directory
        for part in parts:
            path /= part
            resolved = path.resolve(strict=False)
            if (
                _is_link_or_junction(path)
                or not resolved.is_relative_to(self._resolved_run_directory)
            ):
                raise ArtifactIntegrityError(
                    "recorded artifact path escapes run directory"
                )
        return path

    def _verify_recorded_artifact(
        self,
        record: dict[str, object],
    ) -> None:
        target = self._recorded_artifact_path(record)
        byte_size = record["byte_size"]
        sha256 = record["sha256"]
        assert isinstance(byte_size, int)
        assert isinstance(sha256, str)
        try:
            stat = target.stat()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError(
                "recorded artifact file is missing"
            ) from exc
        if (
            byte_size < 0
            or byte_size > self._max_artifact_bytes
            or stat.st_size != byte_size
        ):
            raise ArtifactIntegrityError(
                "recorded artifact byte_size mismatch"
            )
        content = target.read_bytes()
        if len(content) != byte_size or _sha256(content) != sha256:
            raise ArtifactIntegrityError(
                "recorded artifact digest mismatch"
            )

    def _prepare_parent(self, directory_parts: tuple[str, ...]) -> Path:
        current = self.run_directory
        for part in directory_parts:
            current /= part
            current.mkdir(exist_ok=True)
            resolved = current.resolve(strict=True)
            if (
                _is_link_or_junction(current)
                or not current.is_dir()
                or not resolved.is_relative_to(self._resolved_run_directory)
            ):
                raise ArtifactValidationError(
                    "artifact directory must be a real directory"
                )
        return current

    def _remove_durably(self, path: Path, parent: Path) -> bool:
        existed = path.exists()
        path.unlink(missing_ok=True)
        if existed:
            try:
                self._fsync_directory(parent)
            except OSError:
                return False
        return True

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def read(self, ref: ArtifactRef) -> bytes:
        _validate_portable_segment(ref.artifact_id, field_name="artifact_id")
        marker = self._committed_id_path(ref.artifact_id)
        try:
            record = self._read_identity_record(marker, ref.artifact_id)
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError(
                "artifact identity record is missing"
            ) from exc
        if (
            record["relative_path"] != ref.relative_path
            or record["byte_size"] != ref.byte_size
            or record["sha256"] != ref.sha256
        ):
            raise ArtifactIntegrityError(
                "ArtifactRef does not match identity record"
            )
        parts = _artifact_parts(ref.relative_path)
        path = self.run_directory
        for part in parts:
            path /= part
            resolved = path.resolve(strict=False)
            if (
                _is_link_or_junction(path)
                or not resolved.is_relative_to(self._resolved_run_directory)
            ):
                raise ArtifactIntegrityError(
                    "artifact path must not contain symbolic links"
                )
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError("artifact file is missing") from exc
        if stat.st_size != ref.byte_size:
            raise ArtifactIntegrityError("artifact byte_size mismatch")
        if stat.st_size > self._max_artifact_bytes:
            raise ArtifactIntegrityError("artifact exceeds store size limit")

        content = path.read_bytes()
        if len(content) != ref.byte_size:
            raise ArtifactIntegrityError("artifact changed during read")
        if _sha256(content) != ref.sha256:
            raise ArtifactIntegrityError("artifact sha256 mismatch")
        return content
