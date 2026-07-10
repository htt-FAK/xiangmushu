# Release v1.0.0

中文 | English

---

### 🎁 在线体验 / Live Demo

🚀 **点击试用：** <http://118.126.102.143/settings>

*Public test environment, available until November 2026.*
*公开测试环境，可用至 2026 年 11 月。*

---

## 🎉 智能文档生成系统 v1.0.0 / Local RAG-assisted Proposal Writing Platform v1.0.0

**首个正式 release。** 经过完整的 Firecrawl 联网迁移 + 全套文档 overhaul + 品牌升级，项目进入 1.0 稳定状态。

**First official release.** Following the full Firecrawl web-search migration, comprehensive documentation overhaul, and brand upgrade, the project reaches a stable 1.0 baseline.

---

## 🚀 关键变更 / Highlights

### 1. Firecrawl 联网搜索迁移 (`feat(web-search)`)

- 彻底替换 LLM 联网搜索（DashScope `enable_search` + MiMo `web_search` 工具）为 **Firecrawl 免费托管 MCP 客户端**
- 无需 API key，按 IP 限流（search 5/min、scrape 10/min）
- 同步 httpx 自研客户端（保持 `httpx>=0.27,<0.28` 项目 pin，无新依赖）
- 完全删除 `web_search` 模型角色（`model_router` / `provider_registry` / `config` / `frontend` 全链路清理）
- 联网证据注入方式：`prepare_bundle_from_evidence` 把 `WebFact` 列表格式化为 `【联网证据】` 块，拼接到 `ref_texts` 进入提示词
- 失败模式：静默跳过（不回落到 LLM 搜索，保证零费用）
- 12 个新增/重写的测试覆盖 SSE/JSON-RPC/超时/无 key 头/失败模式

### 2. 全套文档 overhaul (`docs`)

**首次补齐 GitHub 门面**：
- `README.md`（605 行双语）：hero + Mermaid 架构图 + P1-P5 痛点表 + 9 条特性 + 6 步快速开始 + 4 组配置表 + 模型支持矩阵 + 项目结构树 + 分层测试哲学
- `LICENSE`（MIT）
- `CONTRIBUTING.md`（双语 157 行：开发环境、commit 规范、PR 流程、代码审查）
- `SECURITY.md`（双语漏洞披露流程）
- `CODE_OF_CONDUCT.md`（Contributor Covenant v2.1）
- `.github/` PR + issue 模板（bug / feature，双语）
- `docs/ARCHITECTURE.md`（英文 230 行技术架构：Mermaid 组件图、后端 20+ 模块清单、模型路由表、Firecrawl 联网流程深度、持久化层）
- `docs/README.md`（中文索引 + 推荐阅读顺序）
- `frontend/README.md`（双语前端开发指南）
- `CHANGELOG.md`（17 条精选 + 90 条完整历史）
- `docs/screenshots/`（6 张 UI 截图）
- `项目计划书.md` 升级 v1.2（§3.2.5 重写为 Firecrawl 架构）

### 3. CI workflow + 行尾规范化 (`chore`)

- `.github/workflows/ci.yml`：Python 3.11 + Node 20 双 job（pytest + offline smoke + `npm run build`），带 pip/npm 缓存，并发 cancel-in-progress
- `.gitattributes`：统一 `* text=auto` + 显式标源文件为 text、二进制为 binary、脚本强制 LF/CRLF；一次性 renormalize 清掉 8 个文件的 CRLF 噪音

### 4. 品牌升级 (`chore(release)`)

- 中文品牌：**项目树** → **智能文档生成系统**
- 英文定位：**xiangmushu** → **Local RAG-assisted Proposal Writing Platform**
- 覆盖 README（hero / 痛点 / 英文对照表 / closing hero）+ docs/ARCHITECTURE.md opening
- 仓库名 / 数据库名 / 目录树 / git clone URL 保留 `xiangmushu`（作为 git repo 标识）

---

## 📊 Commit 总览

```
6e8f7b2 chore(release): rebrand to 智能文档生成系统 + add CI workflow
40fcba9 docs: archive documentation worker session continuations
d76d5a0 chore: add .gitattributes and normalize line endings
2c96012 docs: add bilingual README, LICENSE, community package, and project documentation
b0499fa docs: archive firecrawl migration work plan and evidence
d16966a feat(web-search): replace LLM web search with keyless Firecrawl MCP client
```

---

## 🛠 验证

- ✅ Firecrawl 协议探测（task-1 evidence：stateless POST + SSE + nested `result.content[0].text` JSON-RPC envelope）
- ✅ Firecrawl 真实联网调用返回 5 条结果（`search_web_evidence('python httpx streaming')`）
- ✅ Targeted pytest suite 40 passed in 10.77s
- ✅ Frontend `npm run build` exit 0
- ✅ Independent F1-F4 Final Verification Wave 全部 PASS（F2 记录了 9 条非行为清理债务）
- ✅ Dual-Momus 高精度审查 3 轮通过（Momus + Oracle 双审查，第 3 轮双双 OKAY）

完整证据：`.omo/evidence/task-{1..10}-firecrawl-web-search.txt` + `.omo/evidence/f{1..4}-firecrawl-web-search.txt`

---

## 📚 文档入口

- **[README.md](./README.md)** — 项目门面
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** — 技术架构（英文）
- **[docs/README.md](./docs/README.md)** — 中文文档索引
- **[项目计划书.md](./项目计划书.md)** — 产品规格书 v1.2（含 Firecrawl）
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** — 贡献指南
- **[CHANGELOG.md](./CHANGELOG.md)** — 完整变更历史

---

## 🙏 致谢

DashScope / 通义千问 · Firecrawl · ChromaDB · OpenAI Python SDK · FastAPI · React + Vite

---

*智能文档生成系统* 让申报文档写作从「人工摘抄」走向「RAG 辅助 + 结构化回填」。

*Local RAG-assisted Proposal Writing Platform* turns proposal document writing from "manual copy-paste" into "RAG-assisted + structured fill-back".
