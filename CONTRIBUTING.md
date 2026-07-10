# 贡献指南 / Contributing Guide

感谢你对 xiangmushu (项目树) 项目的关注。我们欢迎任何形式的贡献，包括提交代码、报告问题、改进文档等。

Thank you for your interest in xiangmushu. We welcome contributions of all kinds, including code, bug reports, and documentation improvements.

---

## 行为准则 / Code of Conduct

参与本项目即表示你同意遵守我们的 [行为准则](CODE_OF_CONDUCT.md)。请阅读完整内容，了解哪些行为是被期望的、哪些是不被接受的。

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it in full to understand what is expected.

---

## 开发环境搭建 / Setting Up the Development Environment

### 后端 / Backend

1. 克隆仓库 / Clone the repo:
   ```bash
   git clone https://github.com/<your-username>/xiangmushu.git
   cd xiangmushu
   ```

2. 创建 Python 虚拟环境并安装依赖 / Create a Python virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate        # Linux / macOS
   venv\Scripts\activate           # Windows PowerShell
   pip install -r requirements.txt
   ```

3. 配置环境变量 / Configure environment variables:
   ```bash
   cp .env.example .env
   # 编辑 .env 填入必要的密钥和配置 / Edit .env with required keys and settings
   ```

4. 启动 MySQL 数据库 / Start MySQL:
   确保 MySQL 服务已运行，并且 `.env` 中的数据库连接信息正确。
   Make sure MySQL is running and the connection info in `.env` is correct.

5. 启动后端服务 / Start the backend:
   ```bash
   python server.py
   # 或使用启动脚本 / Or use the launcher script:
   ./start_server.ps1
   ```

### 前端 / Frontend

1. 进入前端目录 / Enter the frontend directory:
   ```bash
   cd frontend
   ```

2. 安装依赖 / Install dependencies:
   ```bash
   npm install
   ```

3. 启动开发服务器 / Start the dev server:
   ```bash
   npm run dev
   ```

4. 构建生产版本 / Build for production:
   ```bash
   npm run build
   ```

---

## 提交规范 / Commit Message Convention

我们遵循 Conventional Commits 规范。提交信息格式 / We follow the Conventional Commits format:

```
<type>(<scope>): <description>
```

示例 / Examples:
- `feat(frontend): add dark mode toggle`
- `fix: resolve race condition in session cleanup`
- `docs: update API reference for /generate`
- `test: add cases for model selection flow`
- `refactor(core): extract template loader into module`

常用 type / Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `ci`.

---

## 提交流程 / Pull Request Process

1. **Fork** 本仓库 / Fork this repository.
2. 从 `main` 创建功能分支 / Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
3. 编写代码，确保通过测试 / Write code and ensure tests pass:
   ```bash
   pytest
   cd frontend && npm run build && cd ..
   ```
4. 提交代码 / Commit your changes (遵循上述规范 / follow the convention above):
   ```bash
   git commit -m "feat(scope): add your feature"
   ```
5. 推送到你的 fork / Push to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```
6. 在 GitHub 上创建 Pull Request / Open a Pull Request on GitHub.

---

## 代码审查 / Code Review

- 每个 PR 至少需要一位维护者审查后方可合并。
- Each PR requires at least one maintainer review before merging.
- 请确保 CI 检查全部通过。
- Please make sure all CI checks pass.
- 审查者请关注：代码质量、测试覆盖、文档更新、安全性。
- Reviewers should focus on: code quality, test coverage, documentation updates, and security.

---

## 报告问题 / Reporting Issues

- 使用 GitHub Issues 报告 bug 或提出功能建议。
- Use GitHub Issues to report bugs or suggest features.
- 提交前请先搜索是否已有类似 issue。
- Please search for existing issues before opening a new one.
- 安全问题请走私有渠道，参考 [SECURITY.md](SECURITY.md)。
- For security issues, please follow the process in [SECURITY.md](SECURITY.md).

---

## 常用命令 / Common Commands

| 操作 / Action | 命令 / Command |
| --- | --- |
| 运行后端测试 / Run backend tests | `pytest` |
| 构建前端 / Build frontend | `cd frontend && npm run build` |
| 启动本地后端 / Start local backend | `python server.py` |
| 启动前端开发 / Start frontend dev | `cd frontend && npm run dev` |
| 一键启动全部 / Launch all services | `./start_server.ps1` |

---

## 许可证 / License

本项目采用 MIT 许可证。提交代码即表示你同意将贡献以相同许可证发布。

This project is licensed under the MIT License. By contributing, you agree that your contributions will be licensed under the same terms.
