from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import config
import server
from core.artifacts import ArtifactNotFoundError, ArtifactObject, local_file_path, put_bytes, put_file
from core.auth import create_access_token, get_or_create_user, init_db


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_put_file_records_size_checksum_and_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STORAGE_PROVIDER", "local")
    monkeypatch.setattr(config, "ARTIFACT_LOCAL_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(server, "mysql_enabled", lambda: False)

    source = tmp_path / "source.txt"
    source.write_text("hello artifact", encoding="utf-8")

    artifact = put_file(source, owner_user_id=12, artifact_type="uploaded_source")

    assert artifact.byte_size == len("hello artifact")
    assert len(artifact.sha256) == 64
    assert local_file_path(artifact).read_text(encoding="utf-8") == "hello artifact"

    text_artifact = put_bytes("parsed text", owner_user_id=12, artifact_type="source_markdown", original_filename="source.md")
    assert text_artifact.byte_size == len("parsed text")
    assert local_file_path(text_artifact).read_text(encoding="utf-8") == "parsed text"

    bad = ArtifactObject(
        id=1,
        artifact_uuid="bad",
        owner_user_id=12,
        artifact_type="generated_doc",
        storage_backend="local",
        bucket_name=None,
        object_key="../../outside.txt",
        original_filename="outside.txt",
        content_type="text/plain",
        byte_size=0,
        sha256="",
    )
    with pytest.raises(Exception):
        local_file_path(bad)


def test_artifact_download_authorizes_owner_and_hides_missing(monkeypatch, tmp_path):
    artifact_file = tmp_path / "artifact.txt"
    artifact_file.write_text("owned", encoding="utf-8")
    artifact = ArtifactObject(
        id=1,
        artifact_uuid="abc",
        owner_user_id=1,
        artifact_type="generated_doc",
        storage_backend="local",
        bucket_name=None,
        object_key="users/1/abc/artifact.txt",
        original_filename="artifact.txt",
        content_type="text/plain",
        byte_size=5,
        sha256="",
    )
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("artifact-owner@example.com", db_path=str(db_path))
    other = get_or_create_user("artifact-other@example.com", db_path=str(db_path))

    monkeypatch.setattr(server, "get_artifact_for_user", lambda uuid, uid: artifact if uid == user.id else None)
    monkeypatch.setattr(server, "local_file_path", lambda item: artifact_file)

    with TestClient(server.app) as client:
        ok = client.get("/api/artifacts/abc/download", headers=_headers(user))
        denied = client.get("/api/artifacts/abc/download", headers=_headers(other))

    assert ok.status_code == 200
    assert ok.text == "owned"
    assert denied.status_code == 404

    monkeypatch.setattr(server, "local_file_path", lambda item: (_ for _ in ()).throw(ArtifactNotFoundError()))
    with TestClient(server.app) as client:
        missing = client.get("/api/artifacts/abc/download", headers=_headers(user))
    assert missing.status_code == 404


def test_legacy_download_compatibility_and_path_traversal(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "OUTPUT_DIR", str(output_dir))
    init_db(str(db_path))
    user = get_or_create_user("legacy@example.com", db_path=str(db_path))
    other = get_or_create_user("other-legacy@example.com", db_path=str(db_path))

    filename = f"demo_u{user.id}_20260612.docx"
    (output_dir / filename).write_bytes(b"doc")

    with TestClient(server.app) as client:
        ok = client.get(f"/api/download/{filename}", headers=_headers(user))
        forbidden = client.get(f"/api/download/{filename}", headers=_headers(other))
        traversal = client.get("/api/download/../secret.docx", headers=_headers(user))

    assert ok.status_code == 200
    assert ok.content == b"doc"
    assert forbidden.status_code == 403
    assert traversal.status_code in {400, 404}
