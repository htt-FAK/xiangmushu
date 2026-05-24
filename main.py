"""
一键启动：启动 FastAPI 后端 + 自动打开 HTML 前端页面
用法: python main.py
"""
from __future__ import annotations

import subprocess
import sys
import time
import atexit
import os
import webbrowser
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
URL = "http://localhost:8502"

_backend_proc: subprocess.Popen | None = None


def _cleanup() -> None:
    """退出时关闭后端进程"""
    global _backend_proc
    if _backend_proc is not None:
        print("[main] 正在关闭 FastAPI 后端...")
        _backend_proc.terminate()
        try:
            _backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _backend_proc.kill()
        print("[main] FastAPI 后端已关闭。")


def _monitor_output(proc: subprocess.Popen) -> None:
    """打印后端日志，直到 uvicorn 启动完成"""
    started = False
    for line in proc.stdout:
        print(f"[server] {line.rstrip()}")
        if not started and "Uvicorn running" in line:
            started = True
            print(f"[main] 后端就绪，打开浏览器 → {URL}")
            webbrowser.open(URL)


def main() -> None:
    global _backend_proc

    atexit.register(_cleanup)

    print(f"[main] 启动 FastAPI 后端 ({URL}) ...")
    _backend_proc = subprocess.Popen(
        [sys.executable, "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        cwd=ROOT,
    )

    # 监控输出，检测到 "Uvicorn running" 时自动打开浏览器
    monitor_thread = threading.Thread(
        target=_monitor_output, args=(_backend_proc,), daemon=True)
    monitor_thread.start()

    # 阻塞等待后端进程结束
    _backend_proc.wait()


if __name__ == "__main__":
    main()
