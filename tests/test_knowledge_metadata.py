from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import config
import server
from core.auth import create_access_token, get_or_create_user, init_db


def _auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


class _FakeVectorStore:
    def __init__(self):
        self.added_chunks = []
        self.deleted = []

    def add_documents(self, chunks):
        self.added_chunks = list(chunks)

    def delete_by_source(self, source: str, knowledge_source_id: int | None = None):
        self.deleted.append((source, knowledge_source_id))

    def collection_exists(self) -> bool:
        return True

    def get_collection_count(self) -> int:
        return len(self.added_chunks)

    def knowledge_metadata_summary(self):
        return {"source_ids": [11], "chunk_keys": ["11:0", "11:1"]}


def test_kb_upload_enriches_chunks_with_mysql_traceability(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("kb@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    fake_vs = _FakeVectorStore()
    persisted_chunks = {}

    monkeypatch.setattr(server, "_get_vs", lambda slug: fake_vs)
    monkeypatch.setattr(server, "mysql_enabled", lambda: True)
    monkeypatch.setattr(
        server,
        "path_to_parsed_document",
        lambda path, original_name="demo.docx": SimpleNamespace(filename=original_name, sections=[], blocks=[]),
    )
    monkeypatch.setattr(
        server._chunker,
        "chunk",
        lambda parsed: [
            SimpleNamespace(id="chunk-a", text="alpha", metadata={"source": parsed.filename}),
            SimpleNamespace(id="chunk-b", text="beta", metadata={"source": parsed.filename}),
        ],
    )
    monkeypatch.setattr(
        server,
        "put_file",
        lambda *args, **kwargs: SimpleNamespace(artifact_uuid="artifact-source"),
    )
    monkeypatch.setattr(
        server,
        "put_bytes",
        lambda *args, **kwargs: SimpleNamespace(artifact_uuid="artifact-parsed"),
    )
    monkeypatch.setattr(
        server,
        "upsert_knowledge_source",
        lambda *args, **kwargs: {"id": 11, "knowledge_base_id": 21, "vector_collection_id": 31},
    )
    monkeypatch.setattr(
        server,
        "replace_source_chunks",
        lambda source_id, kb_id, vector_collection_id, chunks: persisted_chunks.update(
            {
                "source_id": source_id,
                "knowledge_base_id": kb_id,
                "vector_collection_id": vector_collection_id,
                "chunks": list(chunks),
            }
        ),
    )

    with TestClient(server.app) as client:
        response = client.post(
            "/api/kb/upload",
            headers=headers,
            data={"slug": "kb1"},
            files=[("files", ("demo.docx", b"hello world", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
        )

    assert response.status_code == 200
    assert response.json()["results"][0]["ok"] is True
    assert len(fake_vs.added_chunks) == 2
    assert fake_vs.added_chunks[0].metadata["knowledge_source_id"] == 11
    assert fake_vs.added_chunks[0].metadata["knowledge_base_id"] == 21
    assert fake_vs.added_chunks[0].metadata["vector_collection_id"] == 31
    assert fake_vs.added_chunks[0].metadata["knowledge_chunk_key"] == "11:0"
    assert persisted_chunks["source_id"] == 11
    assert persisted_chunks["chunks"][1].metadata["knowledge_chunk_key"] == "11:1"


def test_kb_remove_source_uses_mysql_source_identifier(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("kb-delete@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    fake_vs = _FakeVectorStore()
    monkeypatch.setattr(server, "_get_vs", lambda slug: fake_vs)
    monkeypatch.setattr(server, "remove_source", lambda user_id, slug, source: {"source_id": 11, "knowledge_base_id": 21})

    with TestClient(server.app) as client:
        response = client.post(
            "/api/kb/remove-source",
            headers=headers,
            data={"slug": "kb1", "source": "demo.txt"},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake_vs.deleted == [("demo.txt", 11)]
