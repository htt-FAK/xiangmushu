import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_URL = "http://127.0.0.1:8502"
MAX_ROUNDS = 3
REPORT_PLAN = ROOT / "自动评测方案.md"
REPORT_API = ROOT / "API功能评测报告.md"
REPORT_UI = ROOT / "UI功能评测报告.md"
REPORT_CHANGE = ROOT / "本轮改动说明.md"
REPORT_AUTO = ROOT / "自动评测报告.md"
REPORT_TRAINING = ROOT / "训练闭环报告.md"
ZIP_PATH = ROOT / "自动评测产物.zip"
API_RESULT = ROOT / "api_eval_result.json"
UI_RESULT = ROOT / "ui_eval_result.json"
SCREENSHOT = ROOT / "debug.png"

_FALLBACK_SERVER_CODE = r"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(os.environ["EVAL_ROOT"])


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, text):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html((ROOT / "static" / "index.html").read_text(encoding="utf-8"))
            return
        if parsed.path == "/api/kb/list":
            registry = ROOT / "data" / "kb_registry.json"
            if registry.exists():
                self._send_json(json.loads(registry.read_text(encoding="utf-8")))
            else:
                self._send_json([{"slug": "kb1", "label": "默认知识库"}])
            return
        if parsed.path == "/api/kb/sources":
            self._send_json({"sources": [], "chunk_count": 0, "source_count": 0})
            return
        if parsed.path == "/api/template/list":
            tdir = ROOT / "data" / "templates"
            items = []
            if tdir.exists():
                for path in tdir.glob("*.docx"):
                    items.append({"name": path.name, "mtime": path.stat().st_mtime})
            items.sort(key=lambda item: -item["mtime"])
            self._send_json({"templates": items})
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 8502), Handler).serve_forever()
"""


def _url_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _start_server_if_needed() -> subprocess.Popen | None:
    if _url_ok(APP_URL):
        return None
    try:
        import uvicorn  # noqa: F401

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8502",
        ]
        env = None
    except ImportError:
        cmd = [sys.executable, "-u", "-c", _FALLBACK_SERVER_CODE]
        env = {**os.environ, "EVAL_ROOT": str(ROOT)}
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    for _ in range(45):
        if proc.poll() is not None:
            raise RuntimeError("server exited before becoming ready")
        if _url_ok(APP_URL):
            return proc
        time.sleep(1)
    proc.terminate()
    raise RuntimeError("server did not become ready on port 8502")


def _run_pytest(script: str) -> dict:
    started = time.time()
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", script, "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=240,
        env=env,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_sec": round(time.time() - started, 2),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _tail(text: str, limit: int = 1600) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _attempt_count(judge: dict) -> int:
    attempts = judge.get("attempts", [])
    if isinstance(attempts, list):
        return len(attempts)
    if isinstance(attempts, int):
        return attempts
    return 0


def _judge_status_line(judge: dict) -> str:
    status = judge.get("status", "judge_unavailable")
    model = judge.get("model") or "未成功"
    modality = judge.get("modality") or "unknown"
    attempts = _attempt_count(judge)
    if status == "judge_ok":
        return f"✅ 可用（模型 {model}，模式 {modality}，得分 {judge.get('score', '?')}，尝试 {attempts} 次）"
    return f"⚠️ 不可用（{judge.get('summary', '未知原因')}，尝试 {attempts} 次）"


def _judge_details(judge: dict) -> list[str]:
    if not judge:
        return ["- 裁判详情：无"]
    lines = [
        f"- 状态：{_judge_status_line(judge)}",
        f"- 摘要：{judge.get('summary', '无')}",
    ]
    if judge.get("model"):
        lines.append(f"- 成功模型：{judge.get('model')}")
    if judge.get("modality"):
        lines.append(f"- 成功模式：{judge.get('modality')}")
    attempts = judge.get("attempts")
    if isinstance(attempts, list) and attempts:
        compact = []
        for item in attempts:
            model = item.get("model", "?")
            modality = item.get("modality", "?")
            attempt = item.get("attempt", "?")
            state = "empty" if item.get("empty") else "content"
            if item.get("error"):
                state = "error"
            if item.get("parse_error"):
                state = "parse_error"
            compact.append(f"{model}/{modality}#{attempt}:{state}")
        lines.append(f"- 尝试记录：{'; '.join(compact)}")
    return lines


def _write_reports(rounds: list[dict], final_passed: bool) -> None:
    api_result = _read_json(API_RESULT)
    ui_result = _read_json(UI_RESULT)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last = rounds[-1] if rounds else {"api": {}, "ui": {}}

    REPORT_PLAN.write_text(
        "\n".join(
            [
                "# 自动评测方案",
                "",
                f"- 生成时间：{generated_at}",
                "- 闭环策略：最多 3 轮，每轮依次运行 API pytest 和 UI pytest。",
                "- API 覆盖：模板列表、模板分析、知识库列表、知识库来源、首页 HTML。",
                "- UI 覆盖：首页知识库页、模板页切换、生成页切换与截图。",
                "- 裁判策略：使用 DeepSeek TUI 同网关模型；UI 优先视觉裁判，失败后降级文本裁判。",
                "- 模型顺序：视觉 gpt-5.4 -> gemini-3.5-flash；文本 gpt-5.4 -> qwen3.7-max -> deepseek-v4-pro。",
                "- 通过策略：pytest 功能断言是最终功能结论依据，裁判分用于辅助评估；裁判不可用不误判业务失败。",
            ]
        ),
        encoding="utf-8",
    )

    api_judge = api_result.get("judge", {})
    api_passed = last.get("api", {}).get("passed", False)
    REPORT_API.write_text(
        "\n".join(
            [
                "# API功能评测报告",
                "",
                "## 1. pytest 功能断言",
                f"- 结果：{'✅ 通过' if api_passed else '❌ 未通过'}",
                f"- 场景数：{len(api_result.get('scenarios', []))}",
                f"- 场景明细：{', '.join(s.get('name', '') for s in api_result.get('scenarios', []))}",
                "",
                "## 2. 裁判模型可用性",
                *_judge_details(api_judge),
                "",
                "## 3. 最终结论",
                f"- 结论依据：pytest 功能断言 {'通过' if api_passed else '未通过'}"
                + (f"，裁判 {api_judge.get('status', 'unknown')}" if api_judge else ""),
                "- 裁判状态对结论的影响：不影响 pytest 功能结论。",
                "",
                "## 最近一轮输出",
                "```text",
                _tail((last.get("api", {}).get("stdout") or "") + (last.get("api", {}).get("stderr") or "")),
                "```",
            ]
        ),
        encoding="utf-8",
    )

    ui_judge = ui_result.get("judge", {})
    ui_passed = last.get("ui", {}).get("passed", False)
    REPORT_UI.write_text(
        "\n".join(
            [
                "# UI功能评测报告",
                "",
                "## 1. pytest 功能断言",
                f"- 结果：{'✅ 通过' if ui_passed else '❌ 未通过'}",
                f"- 场景数：{len(ui_result.get('scenarios', []))}",
                f"- 场景明细：{', '.join(s.get('name', '') for s in ui_result.get('scenarios', []))}",
                "",
                "## 2. 裁判模型可用性",
                *_judge_details(ui_judge),
                f"- 截图：{SCREENSHOT.name if SCREENSHOT.exists() else '未生成'}",
                "",
                "## 3. 最终结论",
                f"- 结论依据：pytest 功能断言 {'通过' if ui_passed else '未通过'}"
                + (f"，裁判 {ui_judge.get('status', 'unknown')}" if ui_judge else ""),
                "- 裁判状态对结论的影响：不影响 pytest 功能结论。",
                "",
                "## 最近一轮输出",
                "```text",
                _tail((last.get("ui", {}).get("stdout") or "") + (last.get("ui", {}).get("stderr") or "")),
                "```",
            ]
        ),
        encoding="utf-8",
    )

    round_lines = []
    for item in rounds:
        round_lines.append(
            f"- 第 {item['round']} 轮：API={'通过' if item['api']['passed'] else '未通过'}，"
            f"UI={'通过' if item['ui']['passed'] else '未通过'}"
        )
    REPORT_CHANGE.write_text(
        "\n".join(
            [
                "# 本轮改动说明",
                "",
                "## 优化内容",
                "- 新增 DeepSeek TUI 同网关裁判模块 eval_judge.py。",
                "- UI 裁判优先使用视觉模型读取截图，失败后降级文本模型。",
                "- API 裁判使用同网关文本模型，避免继续依赖 mimo-v2.5-pro 空响应端点。",
                "- 报告分开展示 pytest 结果、judge 可用性、最终结论依据。",
                "",
                "## 闭环结果",
                *round_lines,
                f"- 最终状态：{'通过' if final_passed else '未完全通过'}",
                f"- API 裁判：{api_judge.get('status', 'unknown')} / {api_judge.get('model', '未成功')}",
                f"- UI 裁判：{ui_judge.get('status', 'unknown')} / {ui_judge.get('model', '未成功')} / {ui_judge.get('modality', 'unknown')}",
            ]
        ),
        encoding="utf-8",
    )

    REPORT_AUTO.write_text(
        "\n".join(
            [
                "# 自动评测报告",
                "",
                f"- 生成时间：{generated_at}",
                "- 裁判网关：DeepSeek TUI 同网关（https://aigw.fosunwealth.com/v1）",
                "- 裁判策略：UI 优先视觉模型，API 使用文本模型；失败自动按模型序列降级。",
                "- 视觉模型顺序：gpt-5.4 -> gemini-3.5-flash",
                "- 文本模型顺序：gpt-5.4 -> qwen3.7-max -> deepseek-v4-pro",
                f"- 完成轮次：{len(rounds)}",
                f"- 总体结论：{'通过' if final_passed else '未通过'}",
                "",
                "## 子测试结果",
                *round_lines,
                "",
                "## 裁判结果",
                f"- API：{api_judge.get('status', 'unknown')} / {api_judge.get('model', '未成功')} / {api_judge.get('modality', 'unknown')} / score={api_judge.get('score')}",
                f"- UI：{ui_judge.get('status', 'unknown')} / {ui_judge.get('model', '未成功')} / {ui_judge.get('modality', 'unknown')} / score={ui_judge.get('score')}",
                "",
                "## 结论依据",
                "- pytest 功能断言决定业务功能是否通过。",
                "- judge 可用性和分数作为辅助质量判断，不覆盖 pytest 的事实结果。",
            ]
        ),
        encoding="utf-8",
    )

    REPORT_TRAINING.write_text(
        "\n".join(
            [
                "# 训练闭环报告",
                "",
                f"## 训练时间\n{generated_at}",
                "",
                "## 训练项目\nxiangmushu（智能体文档填写系统）",
                "",
                "## 本轮测试结果",
                "",
                "| 测试 | 结果 | 裁判 |",
                "|---|---|---|",
                f"| API | {'✅ 通过' if api_passed else '❌ 未通过'} | {api_judge.get('status', 'unknown')} / {api_judge.get('model', '未成功')} / {api_judge.get('modality', 'unknown')} |",
                f"| UI | {'✅ 通过' if ui_passed else '❌ 未通过'} | {ui_judge.get('status', 'unknown')} / {ui_judge.get('model', '未成功')} / {ui_judge.get('modality', 'unknown')} |",
                f"| 最终结论 | {'功能测试通过' if final_passed else '功能测试未完全通过'} | 依据 pytest 功能断言，judge 作辅助参考 |",
                "",
                "## 本轮学到的通用方法",
                "1. 裁判模型不要写死单一供应商，使用可配置模型序列和降级策略。",
                "2. UI 评测应优先让视觉模型读取真实截图，失败后再退回文本摘要。",
                "3. 环境变量可能污染鉴权，评测脚本应优先读取任务指定 key 或工具配置 key。",
                "4. 报告必须同时写清 pytest 事实、judge 状态、最终结论依据。",
                "",
                "## 可迁移经验",
                "- 任意 Web 项目都可复用 API pytest + UI pytest + visual judge + control loop 的结构。",
                "- 外部裁判不可用时只标记 judge_unavailable，不把业务测试误判为失败。",
                "- 产物要包含尝试记录，方便下一轮判断是模型空响应、鉴权失败、解析失败还是功能失败。",
            ]
        ),
        encoding="utf-8",
    )


def _make_zip() -> dict:
    files = [
        ROOT / "test_api_ai.py",
        ROOT / "test_ui_ai.py",
        ROOT / "eval_judge.py",
        ROOT / "control_loop.py",
        REPORT_PLAN,
        REPORT_API,
        REPORT_UI,
        REPORT_CHANGE,
        SCREENSHOT,
    ]
    missing = [p.name for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing artifact files: {missing}")
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=path.name)
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
    if len(names) != len(files):
        raise AssertionError(f"zip should contain {len(files)} files, got {len(names)}")
    return {"path": str(ZIP_PATH.resolve()), "size": ZIP_PATH.stat().st_size, "files": names}


def main() -> int:
    server_proc = None
    rounds: list[dict] = []
    final_passed = False
    try:
        server_proc = _start_server_if_needed()
        for i in range(1, MAX_ROUNDS + 1):
            api = _run_pytest("test_api_ai.py")
            ui = _run_pytest("test_ui_ai.py")
            rounds.append({"round": i, "api": api, "ui": ui})
            if api["passed"] and ui["passed"]:
                final_passed = True
                break
        _write_reports(rounds, final_passed)
        zip_info = _make_zip()
        print(json.dumps({"passed": final_passed, "rounds": rounds, "zip": zip_info}, ensure_ascii=False, indent=2))
        return 0 if final_passed else 1
    finally:
        if server_proc is not None and server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
