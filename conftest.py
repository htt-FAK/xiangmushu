"""Shared pytest fixtures for xiangmushu evaluation tests."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
DEFAULT_PORT = 8502


def port_open(port: int = DEFAULT_PORT) -> bool:
    """Check whether a TCP port on 127.0.0.1 is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_server(port: int = DEFAULT_PORT, timeout: int = 45) -> subprocess.Popen:
    """Start the uvicorn server and wait until it is ready.

    Raises RuntimeError if the process exits early or does not become ready
    within *timeout* seconds.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for _ in range(timeout):
        if proc.poll() is not None:
            raise RuntimeError("server exited before becoming ready")
        if port_open(port):
            return proc
        time.sleep(1)
    proc.terminate()
    raise RuntimeError(f"server did not start on port {port}")


def stop_server(proc: subprocess.Popen | None) -> None:
    """Terminate and clean up a server process, if running."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def auto_start_server():
    """Ensure the app server is running for the test session.

    If the server is already listening on the default port, this fixture
    reuses it without starting a new process. Otherwise it starts one and
    tears it down after all tests finish.
    """
    if port_open():
        yield None
        return
    proc = start_server()
    try:
        yield proc
    finally:
        stop_server(proc)
