from pathlib import Path


ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = ROOT / "artifacts" / "auto_eval"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PLAN = ARTIFACT_DIR / "自动评测方案.md"
REPORT_API = ARTIFACT_DIR / "API功能评测报告.md"
REPORT_UI = ARTIFACT_DIR / "UI功能评测报告.md"
REPORT_CHANGE = ARTIFACT_DIR / "本轮改动说明.md"
REPORT_AUTO = ARTIFACT_DIR / "自动评测报告.md"
REPORT_TRAINING = ARTIFACT_DIR / "训练闭环报告.md"
ZIP_PATH = ARTIFACT_DIR / "自动评测产物.zip"
API_RESULT = ARTIFACT_DIR / "api_eval_result.json"
UI_RESULT = ARTIFACT_DIR / "ui_eval_result.json"
SCREENSHOT = ARTIFACT_DIR / "debug.png"
DISCIPLINE_CHECK = ARTIFACT_DIR / "discipline_check.txt"
