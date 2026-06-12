from __future__ import annotations

from dataclasses import dataclass
import hashlib
import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import config
from core.db import mysql_enabled, mysql_transaction


class ArtifactError(RuntimeError):
    pass


class ArtifactNotFoundError(ArtifactError):
    pass


@dataclass(frozen=True)
class ArtifactObject:
    id: int | None
    artifact_uuid: str
    owner_user_id: int
    artifact_type: str
    storage_backend: str
    bucket_name: str | None
    object_key: str
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    status: str = "available"


def _safe_filename(name: str) -> str:
    import re

    value = os.path.basename(name or "artifact")
    value = value.replace("\x00", "").strip()
    value = re.sub(r"[^\w.\-\s\u4e00-\u9fff]", "_", value)
    value = re.sub(r"\.{2,}", ".", value)
    return value or "artifact"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_root() -> Path:
    root = Path(config.ARTIFACT_LOCAL_ROOT)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _local_path_for_key(object_key: str) -> Path:
    root = _local_root()
    target = (root / object_key).resolve()
    if target != root and root not in target.parents:
        raise ArtifactError("Artifact object key escapes local artifact root.")
    return target


def _storage_backend() -> str:
    provider = (config.STORAGE_PROVIDER or "local").strip().lower()
    if provider in {"", "filesystem", "fs"}:
        return "local"
    return provider


def _copy_to_storage(source: Path, object_key: str) -> None:
    backend = _storage_backend()
    if backend != "local":
        raise ArtifactError(f"Artifact storage backend '{backend}' is configured but not implemented yet.")
    target = _local_path_for_key(object_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _write_bytes_to_storage(data: bytes, object_key: str) -> Path:
    backend = _storage_backend()
    if backend != "local":
        raise ArtifactError(f"Artifact storage backend '{backend}' is configured but not implemented yet.")
    target = _local_path_for_key(object_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def put_file(
    source_path: str | os.PathLike[str],
    *,
    owner_user_id: int,
    artifact_type: str,
    original_filename: str | None = None,
    content_type: str | None = None,
    generation_session_id: int | None = None,
    generated_article_id: int | None = None,
    knowledge_source_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> ArtifactObject:
    source = Path(source_path)
    if not source.is_file():
        raise ArtifactNotFoundError("Artifact source file does not exist.")
    artifact_uuid = str(uuid.uuid4())
    filename = _safe_filename(original_filename or source.name)
    object_key = f"users/{int(owner_user_id)}/{artifact_uuid}/{filename}"
    _copy_to_storage(source, object_key)
    stored_path = _local_path_for_key(object_key) if _storage_backend() == "local" else source
    size = stored_path.stat().st_size
    checksum = _sha256(stored_path)
    guessed_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    backend = _storage_backend()
    bucket = config.COS_BUCKET if backend == "tencent_cos" else None
    record_id: int | None = None

    if mysql_enabled():
        import json

        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO artifact_objects(
                        artifact_uuid, owner_user_id, generation_session_id, generated_article_id,
                        knowledge_source_id, artifact_type, storage_backend, bucket_name, object_key,
                        original_filename, content_type, byte_size, sha256, status, visibility, metadata_json
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'available', 'private', %s)
                    """,
                    (
                        artifact_uuid,
                        owner_user_id,
                        generation_session_id,
                        generated_article_id,
                        knowledge_source_id,
                        artifact_type,
                        backend,
                        bucket,
                        object_key,
                        filename,
                        guessed_type,
                        size,
                        checksum,
                        json.dumps(metadata or {}, ensure_ascii=False),
                    ),
                )
                record_id = int(cur.lastrowid)

    return ArtifactObject(
        id=record_id,
        artifact_uuid=artifact_uuid,
        owner_user_id=owner_user_id,
        artifact_type=artifact_type,
        storage_backend=backend,
        bucket_name=bucket,
        object_key=object_key,
        original_filename=filename,
        content_type=guessed_type,
        byte_size=size,
        sha256=checksum,
    )


def put_bytes(
    data: bytes | str,
    *,
    owner_user_id: int,
    artifact_type: str,
    original_filename: str,
    content_type: str | None = None,
    generation_session_id: int | None = None,
    generated_article_id: int | None = None,
    knowledge_source_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> ArtifactObject:
    payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    artifact_uuid = str(uuid.uuid4())
    filename = _safe_filename(original_filename)
    object_key = f"users/{int(owner_user_id)}/{artifact_uuid}/{filename}"
    stored_path = _write_bytes_to_storage(payload, object_key)
    checksum = hashlib.sha256(payload).hexdigest()
    guessed_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    backend = _storage_backend()
    bucket = config.COS_BUCKET if backend == "tencent_cos" else None
    record_id: int | None = None

    if mysql_enabled():
        import json

        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO artifact_objects(
                        artifact_uuid, owner_user_id, generation_session_id, generated_article_id,
                        knowledge_source_id, artifact_type, storage_backend, bucket_name, object_key,
                        original_filename, content_type, byte_size, sha256, status, visibility, metadata_json
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'available', 'private', %s)
                    """,
                    (
                        artifact_uuid,
                        owner_user_id,
                        generation_session_id,
                        generated_article_id,
                        knowledge_source_id,
                        artifact_type,
                        backend,
                        bucket,
                        object_key,
                        filename,
                        guessed_type,
                        stored_path.stat().st_size,
                        checksum,
                        json.dumps(metadata or {}, ensure_ascii=False),
                    ),
                )
                record_id = int(cur.lastrowid)

    return ArtifactObject(
        id=record_id,
        artifact_uuid=artifact_uuid,
        owner_user_id=owner_user_id,
        artifact_type=artifact_type,
        storage_backend=backend,
        bucket_name=bucket,
        object_key=object_key,
        original_filename=filename,
        content_type=guessed_type,
        byte_size=stored_path.stat().st_size,
        sha256=checksum,
    )


def get_artifact_for_user(artifact_uuid: str, owner_user_id: int) -> ArtifactObject | None:
    if not mysql_enabled():
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM artifact_objects
                WHERE artifact_uuid = %s AND owner_user_id = %s AND status = 'available' AND deleted_at IS NULL
                """,
                (artifact_uuid, owner_user_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return ArtifactObject(
        id=int(row["id"]),
        artifact_uuid=str(row["artifact_uuid"]),
        owner_user_id=int(row["owner_user_id"]),
        artifact_type=str(row["artifact_type"]),
        storage_backend=str(row["storage_backend"]),
        bucket_name=row.get("bucket_name"),
        object_key=str(row["object_key"]),
        original_filename=str(row.get("original_filename") or "artifact"),
        content_type=str(row.get("content_type") or "application/octet-stream"),
        byte_size=int(row.get("byte_size") or 0),
        sha256=str(row.get("sha256") or ""),
        status=str(row.get("status") or "available"),
    )


def local_file_path(artifact: ArtifactObject) -> Path:
    if artifact.storage_backend != "local":
        raise ArtifactError(f"Artifact backend '{artifact.storage_backend}' cannot be streamed locally.")
    path = _local_path_for_key(artifact.object_key)
    if not path.is_file():
        raise ArtifactNotFoundError("Artifact file is missing from local storage.")
    return path


def mark_deleted(artifact_uuid: str, owner_user_id: int) -> bool:
    if not mysql_enabled():
        return False
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE artifact_objects
                SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP
                WHERE artifact_uuid = %s AND owner_user_id = %s AND deleted_at IS NULL
                """,
                (artifact_uuid, owner_user_id),
            )
            return bool(cur.rowcount)
