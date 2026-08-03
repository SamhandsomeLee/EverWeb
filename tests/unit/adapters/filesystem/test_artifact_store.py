"""Unit tests for the atomic filesystem ArtifactPort."""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from everweb.adapters.filesystem import (
    ArtifactConflictError,
    ArtifactIntegrityError,
    ArtifactValidationError,
    FilesystemArtifactStore,
    SensitiveArtifactError,
)
from everweb.domain import ArtifactWrite
from everweb.ports import ArtifactPort


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 3, 4, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return 1.0


def create_store(
    tmp_path: Path,
    *,
    max_artifact_bytes: int = 4096,
) -> FilesystemArtifactStore:
    return FilesystemArtifactStore(
        run_root=tmp_path / "run",
        execution_id="execution-001",
        max_artifact_bytes=max_artifact_bytes,
        clock=FixedClock(),
    )


def request(
    *,
    artifact_id: str = "artifact-001",
    relative_path: str = "documents/artifact-001.bin",
    content: Any = b"artifact bytes",
    mime_type: str | None = "application/octet-stream",
) -> ArtifactWrite:
    return ArtifactWrite(
        artifact_id=artifact_id,
        kind="document",
        relative_path=relative_path,
        content=content,
        mime_type=mime_type,
    )


def shared_artifact_files(store: FilesystemArtifactStore) -> list[Path]:
    return [
        path
        for path in store.run_directory.rglob("*")
        if path.is_file()
        and path.relative_to(store.run_directory).parts[0] != ".artifact_ids"
    ]


def test_store_conforms_and_round_trips_bytes_with_consistent_ref(
    tmp_path: Path,
) -> None:
    store: ArtifactPort = create_store(tmp_path)
    content = b"\x89PNG\r\nartifact"

    reference = store.put_bytes(
        request(
            relative_path="screenshots/artifact-001.png",
            content=content,
            mime_type="image/png",
        )
    )

    assert reference.artifact_id == "artifact-001"
    assert reference.kind == "document"
    assert reference.relative_path == "screenshots/artifact-001.png"
    assert reference.sha256 == hashlib.sha256(content).hexdigest()
    assert reference.byte_size == len(content)
    assert reference.mime_type == "image/png"
    assert reference.created_at == FixedClock().now()
    assert reference.redacted is False
    assert store.read(reference) == content


def test_store_writes_canonical_unicode_json(tmp_path: Path) -> None:
    store = create_store(tmp_path)

    reference = store.put_json(
        request(
            relative_path="documents/artifact-001.json",
            content={"标题": "证据", "count": 1},
            mime_type="application/json",
        )
    )

    assert store.read(reference) == (
        '{"count":1,"标题":"证据"}'.encode()
    )


def test_store_rejects_wrong_method_content_and_size(tmp_path: Path) -> None:
    store = create_store(tmp_path, max_artifact_bytes=32)

    with pytest.raises(ArtifactValidationError, match="bytes content"):
        store.put_bytes(request(content={"value": 1}))
    with pytest.raises(ArtifactValidationError, match="JSON content"):
        store.put_json(request(content=b"value"))
    with pytest.raises(ArtifactValidationError, match="limit is 32"):
        store.put_bytes(request(content=b"x" * 33))


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        "artifact.bin",
        "/documents/artifact.bin",
        "../documents/artifact.bin",
        "documents/../artifact.bin",
        r"documents\artifact.bin",
        "official_output/result.json",
        "documents/bad?name",
        "documents/trailing.",
    ],
)
def test_store_rejects_paths_outside_shared_artifact_roots(
    tmp_path: Path,
    relative_path: str,
) -> None:
    store = create_store(tmp_path)

    with pytest.raises(ArtifactValidationError):
        store.put_bytes(request(relative_path=relative_path))


def test_store_never_overwrites_path_or_reuses_id(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    first = store.put_bytes(request(content=b"original"))

    with pytest.raises(ArtifactConflictError):
        store.put_bytes(
            request(
                artifact_id="artifact-002",
                relative_path=first.relative_path,
                content=b"replacement",
            )
        )
    with pytest.raises(ArtifactConflictError):
        store.put_bytes(
            request(
                artifact_id=first.artifact_id,
                relative_path="documents/other.bin",
                content=b"other",
            )
        )

    assert store.read(first) == b"original"


def test_store_rejects_id_reuse_after_recreation(tmp_path: Path) -> None:
    first_store = create_store(tmp_path)
    first_store.put_bytes(request())
    reopened_store = create_store(tmp_path)

    with pytest.raises(ArtifactConflictError, match="artifact_id"):
        reopened_store.put_bytes(
            request(relative_path="documents/other.bin")
        )


def test_concurrent_stores_cannot_reuse_artifact_id(tmp_path: Path) -> None:
    stores = (create_store(tmp_path), create_store(tmp_path))
    barrier = threading.Barrier(2)

    def put(index: int) -> str:
        barrier.wait()
        try:
            stores[index].put_bytes(
                request(relative_path=f"documents/artifact-{index}.bin")
            )
        except ArtifactConflictError:
            return "conflict"
        return "written"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(put, range(2)))

    assert sorted(results) == ["conflict", "written"]
    reopened = create_store(tmp_path)
    with pytest.raises(ArtifactConflictError):
        reopened.put_bytes(
            request(relative_path="documents/third.bin")
        )


@pytest.mark.parametrize(
    "content",
    [
        b"Authorization: Bearer secret",
        b"Cookie=sessionid=secret",
        b"Set-Cookie: token=secret",
        b"api_key=secret",
        b"https://example.test/?token=secret",
        b"reasoning: private chain",
        '{"accessToken":"secret"}'.encode("utf-16"),
        b"\xff" + '{"accessToken":"secret"}'.encode("utf-16-le") + b"\xfe",
        {"token": "secret"},
        {"access_token": "secret"},
        {"session_id": "secret"},
        {"client_secret": "secret"},
        {"provider_reasoning": "private chain"},
        {"url": "https://example.test/?code=secret"},
    ],
)
def test_store_rejects_sensitive_shared_content_without_files(
    tmp_path: Path,
    content: Any,
) -> None:
    store = create_store(tmp_path)
    write = request(
        relative_path="diagnostics/artifact-001.json",
        content=content,
    )

    with pytest.raises(SensitiveArtifactError):
        if isinstance(content, bytes):
            store.put_bytes(write)
        else:
            store.put_json(write)

    assert shared_artifact_files(store) == []


def test_store_scans_shareable_metadata(tmp_path: Path) -> None:
    store = create_store(tmp_path)

    with pytest.raises(SensitiveArtifactError):
        store.put_bytes(
            request(mime_type="Authorization: Bearer secret")
        )

    assert shared_artifact_files(store) == []


def test_store_rejects_symlinked_artifact_directory(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (store.run_directory / "documents").symlink_to(
            outside,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(ArtifactValidationError, match="real directory"):
        store.put_bytes(request())

    assert list(outside.iterdir()) == []


def test_store_rejects_symlinked_identity_directory(tmp_path: Path) -> None:
    run_directory = tmp_path / "run" / "execution-001"
    run_directory.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (run_directory / ".artifact_ids").symlink_to(
            outside,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(
        ArtifactValidationError,
        match="identity directory",
    ):
        create_store(tmp_path)

    assert list(outside.iterdir()) == []


def test_store_rejects_symlinked_lock_file(tmp_path: Path) -> None:
    identity_directory = (
        tmp_path / "run" / "execution-001" / ".artifact_ids"
    )
    identity_directory.mkdir(parents=True)
    outside = tmp_path / "outside.lock"
    outside.write_bytes(b"unchanged")
    try:
        (identity_directory / ".store.lock").symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(ArtifactValidationError, match="lock"):
        create_store(tmp_path)

    assert outside.read_bytes() == b"unchanged"


def test_read_fails_closed_when_size_or_digest_changes(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    reference = store.put_bytes(request(content=b"original"))
    path = store.run_directory / reference.relative_path

    path.write_bytes(b"longer replacement")
    with pytest.raises(ArtifactIntegrityError, match="byte_size"):
        store.read(reference)

    path.write_bytes(b"tampered")
    same_size_reference = reference.model_copy(
        update={"byte_size": len(b"tampered")}
    )
    with pytest.raises(ArtifactIntegrityError, match="sha256"):
        store.read(same_size_reference)
