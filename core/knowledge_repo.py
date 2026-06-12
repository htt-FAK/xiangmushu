from __future__ import annotations

import json
import os
import re
from typing import Any

import config
from core.db import mysql_enabled, mysql_transaction

REGISTRY_PATH = os.path.join(os.path.dirname(config.__file__), "data", "kb_registry.json")
COLLECTION_PREFIX = "plan_kb__"


def _ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)


def slugify(label: str) -> str:
    value = (label or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_") or "kb"
    return value[:32]


def collection_name_for_slug(slug: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "", str(slug or "").lower())
    if not safe:
        safe = "default"
    return f"{COLLECTION_PREFIX}{safe}"


def default_registry() -> list[dict[str, Any]]:
    return [
        {"slug": "kb1", "label": "知识库 1"},
        {"slug": "kb2", "label": "知识库 2"},
    ]


def _load_json_registry() -> list[dict[str, Any]]:
    _ensure_data_dir()
    if not os.path.isfile(REGISTRY_PATH):
        data = default_registry()
        _save_json_registry(data)
        return data
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list) or not data:
            data = default_registry()
            _save_json_registry(data)
        return data
    except (json.JSONDecodeError, OSError):
        data = default_registry()
        _save_json_registry(data)
        return data


def _save_json_registry(entries: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(REGISTRY_PATH, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)


def list_knowledge_bases(user_id: int | None = None) -> list[dict[str, Any]]:
    if not mysql_enabled() or user_id is None:
        return list(_load_json_registry())
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, label, status, description, created_at, updated_at
                FROM knowledge_bases
                WHERE owner_user_id = %s AND deleted_at IS NULL
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    if not rows:
        seeds = default_registry()
        for item in seeds:
            create_knowledge_base(user_id, item["label"], item["slug"])
        return list_knowledge_bases(user_id)
    return [
        {
            "id": int(row["id"]),
            "slug": str(row["slug"]),
            "label": str(row["label"]),
            "status": str(row.get("status") or "active"),
            "description": row.get("description"),
        }
        for row in rows
    ]


def create_knowledge_base(user_id: int | None, label: str, slug: str | None = None) -> str:
    if not mysql_enabled() or user_id is None:
        registry = _load_json_registry()
        base = (slug or slugify(label)).lower()
        base = re.sub(r"[^a-z0-9_]", "", base) or "kb"
        next_slug = base
        index = 2
        while any(item["slug"] == next_slug for item in registry):
            next_slug = f"{base}_{index}"
            index += 1
        registry.append({"slug": next_slug, "label": (label or next_slug).strip() or next_slug})
        _save_json_registry(registry)
        return next_slug
    base = (slug or slugify(label)).lower()
    base = re.sub(r"[^a-z0-9_]", "", base) or "kb"
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            next_slug = base
            index = 2
            while True:
                cur.execute(
                    "SELECT id FROM knowledge_bases WHERE owner_user_id = %s AND slug = %s AND deleted_at IS NULL",
                    (user_id, next_slug),
                )
                if not cur.fetchone():
                    break
                next_slug = f"{base}_{index}"
                index += 1
            cur.execute(
                """
                INSERT INTO knowledge_bases(owner_user_id, slug, label, status)
                VALUES(%s, %s, %s, 'active')
                """,
                (user_id, next_slug, (label or next_slug).strip() or next_slug),
            )
            cur.execute(
                """
                INSERT INTO vector_collections(knowledge_base_id, backend, collection_name, embedding_model, status)
                VALUES(LAST_INSERT_ID(), 'chroma', %s, %s, 'active')
                """,
                (collection_name_for_slug(next_slug), config.EMBEDDING_MODEL),
            )
    return next_slug


def delete_knowledge_base(user_id: int | None, slug: str) -> None:
    if not mysql_enabled() or user_id is None:
        registry = _load_json_registry()
        if len(registry) <= 1:
            raise ValueError("至少保留一个知识库")
        new_registry = [item for item in registry if item["slug"] != slug]
        if len(new_registry) != len(registry):
            _save_json_registry(new_registry)
        return
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS count FROM knowledge_bases WHERE owner_user_id = %s AND deleted_at IS NULL",
                (user_id,),
            )
            total = int(cur.fetchone()["count"] or 0)
            if total <= 1:
                raise ValueError("至少保留一个知识库")
            cur.execute(
                """
                UPDATE knowledge_bases
                SET deleted_at = CURRENT_TIMESTAMP, status = 'deleted'
                WHERE owner_user_id = %s AND slug = %s AND deleted_at IS NULL
                """,
                (user_id, slug),
            )


def get_knowledge_base(user_id: int, slug: str) -> dict[str, Any] | None:
    if not mysql_enabled():
        for item in _load_json_registry():
            if item["slug"] == slug:
                return dict(item)
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT kb.id, kb.slug, kb.label, kb.status, vc.id AS vector_collection_id,
                       vc.collection_name, vc.backend
                FROM knowledge_bases kb
                LEFT JOIN vector_collections vc
                    ON vc.knowledge_base_id = kb.id AND vc.status = 'active'
                WHERE kb.owner_user_id = %s AND kb.slug = %s AND kb.deleted_at IS NULL
                LIMIT 1
                """,
                (user_id, slug),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "slug": str(row["slug"]),
        "label": str(row["label"]),
        "status": str(row.get("status") or "active"),
        "vector_collection_id": int(row["vector_collection_id"]) if row.get("vector_collection_id") else None,
        "collection_name": row.get("collection_name"),
        "backend": row.get("backend") or "chroma",
    }


def ensure_vector_collection(user_id: int, slug: str) -> dict[str, Any] | None:
    if not mysql_enabled():
        return None
    kb = get_knowledge_base(user_id, slug)
    if kb is None:
        create_knowledge_base(user_id, slug, slug)
        kb = get_knowledge_base(user_id, slug)
    assert kb is not None
    if kb.get("vector_collection_id"):
        return kb
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vector_collections(knowledge_base_id, backend, collection_name, embedding_model, status)
                VALUES(%s, 'chroma', %s, %s, 'active')
                ON DUPLICATE KEY UPDATE embedding_model = VALUES(embedding_model), status = 'active'
                """,
                (kb["id"], collection_name_for_slug(slug), config.EMBEDDING_MODEL),
            )
    return get_knowledge_base(user_id, slug)


def _artifact_id_for_uuid(cur: Any, artifact_uuid: str | None) -> int | None:
    if not artifact_uuid:
        return None
    cur.execute("SELECT id FROM artifact_objects WHERE artifact_uuid = %s LIMIT 1", (artifact_uuid,))
    row = cur.fetchone()
    return int(row["id"]) if row else None


def upsert_knowledge_source(
    user_id: int,
    slug: str,
    filename: str,
    *,
    original_artifact_uuid: str | None = None,
    parsed_artifact_uuid: str | None = None,
    content_type: str | None = None,
    byte_size: int = 0,
    sha256: str | None = None,
    status: str = "uploaded",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not mysql_enabled():
        return None
    kb = ensure_vector_collection(user_id, slug)
    assert kb is not None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            original_artifact_id = _artifact_id_for_uuid(cur, original_artifact_uuid)
            parsed_artifact_id = _artifact_id_for_uuid(cur, parsed_artifact_uuid)
            cur.execute(
                """
                SELECT id FROM knowledge_sources
                WHERE knowledge_base_id = %s AND owner_user_id = %s AND original_filename = %s AND deleted_at IS NULL
                LIMIT 1
                """,
                (kb["id"], user_id, filename),
            )
            existing = cur.fetchone()
            payload = json.dumps(metadata or {}, ensure_ascii=False)
            if existing:
                source_id = int(existing["id"])
                cur.execute(
                    """
                    UPDATE knowledge_sources
                    SET original_artifact_id = %s,
                        parsed_artifact_id = %s,
                        content_type = %s,
                        byte_size = %s,
                        sha256 = %s,
                        status = %s,
                        metadata_json = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        original_artifact_id,
                        parsed_artifact_id,
                        content_type,
                        byte_size,
                        sha256,
                        status,
                        payload,
                        source_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO knowledge_sources(
                        knowledge_base_id, owner_user_id, original_artifact_id, parsed_artifact_id,
                        original_filename, content_type, byte_size, sha256, status, metadata_json
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        kb["id"],
                        user_id,
                        original_artifact_id,
                        parsed_artifact_id,
                        filename,
                        content_type,
                        byte_size,
                        sha256,
                        status,
                        payload,
                    ),
                )
                source_id = int(cur.lastrowid)
    return {"id": source_id, "knowledge_base_id": kb["id"], "vector_collection_id": kb.get("vector_collection_id")}


def replace_source_chunks(
    source_id: int,
    knowledge_base_id: int,
    vector_collection_id: int | None,
    chunks: list[Any],
) -> None:
    if not mysql_enabled():
        return
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_chunks WHERE knowledge_source_id = %s", (source_id,))
            for index, chunk in enumerate(chunks):
                metadata = dict(getattr(chunk, "metadata", {}) or {})
                cur.execute(
                    """
                    INSERT INTO knowledge_chunks(
                        knowledge_source_id, knowledge_base_id, vector_collection_id, chunk_key, chunk_index,
                        content_sha256, char_start, char_end, token_count, chroma_id, metadata_json, status
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s, %s, 'indexed')
                    """,
                    (
                        source_id,
                        knowledge_base_id,
                        vector_collection_id,
                        f"{source_id}:{index}",
                        index,
                        metadata.get("chunk_sha256"),
                        getattr(chunk, "id", ""),
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
            cur.execute(
                """
                UPDATE knowledge_sources
                SET status = 'indexed', indexed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (source_id,),
            )


def list_source_stats(
    user_id: int,
    slug: str,
    collection_exists: bool,
    vector_count: int,
    metadata_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata_summary = metadata_summary or {"source_ids": [], "chunk_keys": []}
    if not mysql_enabled():
        return {"sources": [], "source_count": 0, "integrity": {"collection_exists": collection_exists, "vector_count": vector_count}}
    kb = get_knowledge_base(user_id, slug)
    if kb is None:
        return {"sources": [], "source_count": 0, "integrity": {"collection_exists": collection_exists, "vector_count": vector_count}}
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, original_filename, status
                FROM knowledge_sources
                WHERE knowledge_base_id = %s AND owner_user_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                (kb["id"], user_id),
            )
            source_rows = cur.fetchall()
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM knowledge_chunks
                WHERE knowledge_base_id = %s AND status = 'indexed'
                """,
                (kb["id"],),
            )
            chunk_count = int(cur.fetchone()["count"] or 0)
            cur.execute(
                """
                SELECT id
                FROM knowledge_sources
                WHERE knowledge_base_id = %s AND owner_user_id = %s AND deleted_at IS NULL
                """,
                (kb["id"], user_id),
            )
            known_source_ids = {int(row["id"]) for row in cur.fetchall()}
    vector_source_ids = {
        int(item)
        for item in (metadata_summary.get("source_ids") or [])
        if str(item).strip()
    }
    missing_source_rows = sorted(vector_source_ids - known_source_ids)
    return {
        "sources": [str(row["original_filename"]) for row in source_rows],
        "source_count": len(source_rows),
        "chunk_count": chunk_count,
        "integrity": {
            "collection_exists": collection_exists,
            "vector_count": vector_count,
            "missing_collection": not collection_exists,
            "count_mismatch": collection_exists and chunk_count != vector_count,
            "missing_source_rows": missing_source_rows,
        },
    }


def remove_source(user_id: int, slug: str, source: str) -> dict[str, Any] | None:
    if not mysql_enabled():
        return None
    kb = get_knowledge_base(user_id, slug)
    if kb is None:
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM knowledge_sources
                WHERE knowledge_base_id = %s AND owner_user_id = %s AND original_filename = %s AND deleted_at IS NULL
                LIMIT 1
                """,
                (kb["id"], user_id, source),
            )
            row = cur.fetchone()
            if not row:
                return None
            source_id = int(row["id"])
            cur.execute("UPDATE knowledge_sources SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP WHERE id = %s", (source_id,))
            cur.execute("DELETE FROM knowledge_chunks WHERE knowledge_source_id = %s", (source_id,))
    return {"source_id": source_id, "knowledge_base_id": kb["id"]}
