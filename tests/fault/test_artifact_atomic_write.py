"""Fault tests for atomic artifact publication."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import pytest

from everweb.adapters.filesystem import (
    ArtifactConflictError,
    ArtifactIntegrityError,
    FilesystemArtifactStore,
)
from everweb.domain import ArtifactWrite


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 3, 4, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def store(tmp_path: Path) -> FilesystemArtifactStore:
    return FilesystemArtifactStore(
        run_root=tmp_path / "run",
        execution_id="execution-001",
        max_artifact_bytes=4096,
        clock=FixedClock(),
    )


def write() -> ArtifactWrite:
    return ArtifactWrite(
        artifact_id="artifact-001",
        kind="document",
        relative_path="documents/artifact-001.bin",
        content=b"content",
        mime_type="application/octet-stream",
    )


def assert_no_artifact_files(artifact_store: FilesystemArtifactStore) -> None:
    files = [
        path
        for path in artifact_store.run_directory.rglob("*")
        if path.is_file()
        and path.relative_to(artifact_store.run_directory).parts[0]
        != ".artifact_ids"
    ]
    assert files == []


def raise_disk_error(*_args: object, **_kwargs: object) -> NoReturn:
    raise OSError("injected disk failure")


def test_fsync_failure_leaves_no_temporary_or_final_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = store(tmp_path)
    monkeypatch.setattr(
        "everweb.adapters.filesystem.artifact_store.os.fsync",
        raise_disk_error,
    )

    with pytest.raises(OSError, match="injected disk failure"):
        artifact_store.put_bytes(write())

    assert_no_artifact_files(artifact_store)
    monkeypatch.undo()
    reopened = store(tmp_path)
    reference = reopened.put_bytes(write())
    assert reopened.read(reference) == b"content"


def test_atomic_publish_failure_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = store(tmp_path)
    monkeypatch.setattr(
        "everweb.adapters.filesystem.artifact_store.os.link",
        raise_disk_error,
    )

    with pytest.raises(OSError, match="injected disk failure"):
        artifact_store.put_bytes(write())

    assert_no_artifact_files(artifact_store)


def test_read_back_mismatch_blocks_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = store(tmp_path)
    original_read_bytes = Path.read_bytes

    def corrupted_read(path: Path) -> bytes:
        if path.suffix == ".tmp":
            return b"corrupted"
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", corrupted_read)

    with pytest.raises(ArtifactIntegrityError, match="read-back mismatch"):
        artifact_store.put_bytes(write())

    assert_no_artifact_files(artifact_store)


def test_directory_fsync_failure_rolls_back_published_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = store(tmp_path)
    original_fsync_directory = artifact_store._fsync_directory

    def fail_for_artifact_directory(directory: Path) -> None:
        if directory.name == "documents":
            raise_disk_error()
        original_fsync_directory(directory)

    monkeypatch.setattr(
        artifact_store,
        "_fsync_directory",
        fail_for_artifact_directory,
    )

    with pytest.raises(OSError, match="injected disk failure"):
        artifact_store.put_bytes(write())

    assert_no_artifact_files(artifact_store)
    monkeypatch.undo()
    reopened = store(tmp_path)
    reference = reopened.put_bytes(write())
    assert reopened.read(reference) == b"content"


def test_recreation_discards_crashed_pending_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = store(tmp_path)
    monkeypatch.setattr(
        "everweb.adapters.filesystem.artifact_store.os.link",
        lambda *_args: (_ for _ in ()).throw(SystemExit("crash")),
    )

    with pytest.raises(SystemExit, match="crash"):
        artifact_store.put_bytes(write())

    monkeypatch.undo()
    reopened = store(tmp_path)
    reference = reopened.put_bytes(write())
    assert reopened.read(reference) == b"content"


def test_recreation_commits_crashed_published_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_store = store(tmp_path)
    original_fsync_directory = artifact_store._fsync_directory

    def crash_after_publish(directory: Path) -> None:
        if directory.name == "documents":
            raise SystemExit("crash")
        original_fsync_directory(directory)

    monkeypatch.setattr(
        artifact_store,
        "_fsync_directory",
        crash_after_publish,
    )

    with pytest.raises(SystemExit, match="crash"):
        artifact_store.put_bytes(write())

    reopened = store(tmp_path)
    with pytest.raises(ArtifactConflictError, match="artifact_id already exists"):
        reopened.put_bytes(
            write().model_copy(
                update={"relative_path": "documents/other.bin"}
            )
        )
