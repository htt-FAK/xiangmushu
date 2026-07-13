# Proposal: 自定义内容审核模型 (Custom Content Audit Model)

## Why

当前系统的内容审核 (`content_auditor.py` / `AUDIT_TEXT_MODEL`) 固定使用 qwen3.6-flash 作为主要审核模型。对于需要频繁生成文档的用户，每次生成都会多次调用审核模型（按片段数计），成本累积显著。部分用户手里已经有更便宜的 OpenAI 兼容模型（如商汤 SenseNova、Moonshot、字节豆包、百川等），但系统目前仅支持 3 个固定供应商 (dashscope/deepseek/mimo)。

引入"自定义审核模型"让用户能用自己的 OpenAI 兼容 API 接入审核环节，**在不降低审核质量的前提下显著降低 API 成本**。

选择从内容审核切入而非生成环节，原因有三：
1. 审核模型对模型能力的要求远低于生成模型（只需要判定 pass/fail 并输出少量文字），OpenAI 兼容模型几乎都能胜任；
2. 审核失败可以安全地 fallback 到默认模型，不影响主线生成流程的稳定性；
3. 不触碰现有 provider registry 的 200+ 行代码，变更风险可控。

## What Changes

- **新增 DB 表**：`user_custom_audit_models` 存储每用户的自定义审核模型配置（base_url / model_id / 加密 api_key / 验证状态）
- **新增后端模块**：`core/custom_audit.py` 负责 CRUD、加密（复用 `billing.encrypt_api_key`）、测试连通（复用 `api_key_validation.probe_api_key_model`）
- **新增 3 个 API 端点**：
  - `GET /api/user/custom-audit-model` — 查询当前用户的配置
  - `POST /api/user/custom-audit-model` — **测试失败时直接拒绝保存**（422 + 详细错误）
  - `DELETE /api/user/custom-audit-model` — 删除配置，自动回退到默认审核模型
- **修改 `core/content_auditor.py`**：在每次审核调用前查询用户自定义配置，存在则使用自定义 client；调用失败时自动 fallback 到默认 `AUDIT_TEXT_MODEL` 并在返回结果中标记 fallback 事件
- **新增前端 Settings 页面卡片**：在现有三张 provider 卡下方新增"自定义内容审核模型"独立区块，含 base_url / model_id / api_key 三个输入框 + 测试并保存 / 删除按钮 + 状态展示
- **新增 i18n 翻译 keys**：约 15 个新的中英文翻译条目
- **生成结果展示 fallback 提示（B 方案弱提示）**：当 `content_auditor` 触发 fallback，在 `/generate` 页面的"运行概览"区域显示非阻塞提示 banner，列出失败次数 + 自定义模型名 + 默认模型名 + 错误摘要 + "前往设置"链接

## Capabilities

### New Capabilities

- `custom-audit-model`: 用户在 Settings 页面配置自己持有的任意 OpenAI 兼容模型作为内容审核 (content audit) 的模型来源；系统需支持测试时验证失败拒绝保存、运行时失败自动 fallback 到默认模型并以弱提示 (方案 B) 通知用户。

### Modified Capabilities

（无需修改现有 spec；本变更仅新增独立的能力模块，不改变现有审核流程的开关语义、不改 provider registry 的语义、不改用户 API Key 的语义。）

## Impact

### Affected Code

- **后端** (Python, FastAPI)
  - 新增 `core/custom_audit.py` (~120 行)
  - 新增 `migrations/mysql/005_user_custom_audit_models.sql` (~20 行)
  - 修改 `core/content_auditor.py` (+`_resolve_audit_client` 方法, ~30 行)
  - 修改 `server.py` 新增 3 个 endpoint (~50 行)
  - 可选：在 `core/provider_clients.py` 新增 helper `custom_openai_client()` (+15 行)

- **前端** (React/TypeScript)
  - 新增 Settings 卡片组件 (~150 行)
  - 修改 `frontend/src/api.ts` 新增 3 个 wrapper 函数 (+30 行)
  - 修改 `frontend/src/i18n.ts` 新增约 15 个 keys
  - 生成结果页面新增 fallback banner (~50 行)

### Affected APIs

- **新增**
  - `GET  /api/user/custom-audit-model`
  - `POST /api/user/custom-audit-model` (body: `{name, base_url, model_id, api_key}`; 2xx 仅在 probe 通过时返回; 422 表示 probe 失败且拒绝保存)
  - `DELETE /api/user/custom-audit-model`

- **隐式变化**
  - `POST /api/generate` 和 `POST /api/generate/sessions` 的返回 payload 增加可选字段 `audit_fallback_events: list[{model_id, error, count}]` 用于前端展示 fallback 提示

### Dependencies

- 复用现有 Fernet 加密（`billing.encrypt_api_key` / `decrypt_api_key`）
- 复用现有 OpenAI SDK 客户端构建流程（`openai.OpenAI(api_key=..., base_url=...)`）
- 复用现有 probe 函数（`api_key_validation.probe_api_key_model`）

### Systems

- **数据库**: 新增一张表，需要在 MySQL 持久化模式上跑 `005_user_custom_audit_models.sql`；SQLite 模式下同表结构自动创建（参考现有 `user_provider_api_keys` 的 inline DDL 模式）
- **无破坏性变更**: 默认无配置的用户保持现有行为（始终用 `AUDIT_TEXT_MODEL`）
