# xiangmushu Project Instructions

This file is the project-level instruction set for DeepSeek TUI / Ace when
working inside `xiangmushu`.

## Project summary

- Type: Python web project
- Core app files: `app.py`, `server.py`, `config.py`
- Core logic: `core/`
- Frontend: `frontend/`, `static/`
- Tests: `test_*.py`, `conftest.py`
- Durable docs: `docs/`

## Agent Artifact Rules

When working in this project, generated files must be stored by purpose instead
of being dropped into the repo root.

### Storage rules

- Evaluation outputs go to `artifacts/auto_eval/`
  - reports: `自动评测方案.md`, `API功能评测报告.md`, `UI功能评测报告.md`,
    `本轮改动说明.md`, `自动评测报告.md`, `训练闭环报告.md`
  - machine-readable results: `api_eval_result.json`, `ui_eval_result.json`
  - screenshots and bundles: `debug.png`, `自动评测产物.zip`
- One-off temporary checks should also stay under `artifacts/`, not the repo
  root.
- Reusable source code belongs in tracked folders such as `scripts/`, `docs/`,
  `core/`, `frontend/`, and tests. Only place a file there if it is intended to
  be kept and versioned.

### Git rules

- Do not commit generated evaluation artifacts.
- Before staging changes, exclude anything under `artifacts/` and other
  generated screenshots, zips, or result dumps.
- If an artifact was accidentally created in the repo root, move it into
  `artifacts/` before finishing the task.

### End-of-task rules

- In the final report, state the artifact directory that was used.
- Report the main deliverable path explicitly instead of only naming the file.
- If no durable artifact is needed, do not create one just for completeness.

## Working style for this project

- Prefer small, verifiable changes.
- Do not modify `.env`, secrets, database source data, or user-uploaded files
  unless the user explicitly asks.
- Separate `pytest` results from judge/model availability in reports.
- Treat generated artifacts as runtime output, not source code.
