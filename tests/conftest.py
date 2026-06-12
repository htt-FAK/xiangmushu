from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest
import requests

import config


@pytest.fixture(autouse=True)
def _default_tests_to_sqlite(monkeypatch):
    monkeypatch.setattr(config, "PERSISTENCE_MODE", "sqlite", raising=False)
    monkeypatch.setattr(config, "PERSISTENCE_SQLITE_FALLBACK", True, raising=False)


@pytest.fixture
def auto_start_server():
    root = Path(__file__).resolve().parents[1]
    temp_dir = root / "data" / ".test-runtime"
    temp_dir.mkdir(parents=True, exist_ok=True)
    auth_db_path = temp_dir / "auth-ui.sqlite3"

    previous_auth_db = config.AUTH_DB_PATH
    config.AUTH_DB_PATH = str(auth_db_path)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["PERSISTENCE_MODE"] = "sqlite"
    env["PERSISTENCE_SQLITE_FALLBACK"] = "1"
    env["AUTH_DB_PATH"] = str(auth_db_path)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                response = requests.get(f"{base_url}/", timeout=2)
                if response.status_code < 500:
                    yield base_url
                    return
            except Exception:
                time.sleep(1)
        pytest.skip("Local UI server did not become ready in time.")
    finally:
        config.AUTH_DB_PATH = previous_auth_db
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
