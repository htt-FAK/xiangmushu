from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import config
from core.artifacts import cos_presigned_download_url, materialize_artifact, put_file


def main() -> int:
    backend = (config.STORAGE_PROVIDER or "").strip().lower()
    if backend != "tencent_cos":
        raise SystemExit("STORAGE_PROVIDER must be set to tencent_cos for this smoke test.")

    payload = b"xiangmushu-cos-smoke-test\n"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(payload)
        source_path = Path(tmp.name)

    download_path: Path | None = None
    try:
        artifact = put_file(
            source_path,
            owner_user_id=0,
            artifact_type="smoke_test",
            original_filename="cos-smoke-test.txt",
            content_type="text/plain",
            metadata={"source": "scripts/smoke_test_cos_artifacts.py"},
        )
        download_path, should_cleanup = materialize_artifact(artifact)
        downloaded = download_path.read_bytes()
        signed_url = cos_presigned_download_url(artifact)
        result = {
            "ok": downloaded == payload,
            "storage_backend": artifact.storage_backend,
            "bucket_name": artifact.bucket_name,
            "object_key": artifact.object_key,
            "byte_size": artifact.byte_size,
            "signed_url_prefix": signed_url[:160],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            raise SystemExit("Downloaded payload does not match uploaded payload.")
        if should_cleanup:
            download_path.unlink(missing_ok=True)
        return 0
    finally:
        source_path.unlink(missing_ok=True)
        if download_path is not None:
            download_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
