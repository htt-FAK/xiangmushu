# Design: 自定义内容审核模型

## Context

**当前状态**：`core/content_auditor.py` 在每次生成流程的 `generate_one_task()` 内部，对每个生成片段调用一次内容审核。当前通过 `AUDIT_TEXT_MODEL` 环境变量（默认 `qwen3.6-flash`）固定指向一个审核模型，由平台 `DASHSCOPE_API_KEY` 或用户已配置的 dashscope provider key 提供认证。

**痛点**：
- 用户无法用自己持有的更便宜的 OpenAI 兼容 API（如商汤、Moonshot、百川等）来承担审核成本
- 现有 provider 系统（`core/provider_registry.py`, `core/provider_clients.py`, `core/billing.py`）是为 dashscope/deepseek/mimo 三个固定供应商设计的，硬编码很深，扩展为 N 个任意供应商需要改 8+ 个文件
- 现有 `user-api-key` capability 是为"用户 BYOK 用于生成"设计的，与"用户 BYOK 仅用于审核"的诉求不一致

**约束**：
- 审核模型对能力要求低（pass/fail 判定 + 少量文字）→ 任何主流 OpenAI 兼容模型都能胜任
- 审核失败**不能**影响主线生成流程的稳定性（必须能自动 fallback）
- 用户必须能在测试阶段就发现配置错误（避免上线后才暴露问题）

## Goals / Non-Goals

**Goals:**
- 用户可以在 Settings 页面配置一个 OpenAI 兼容的自定义审核模型（base_url + api_key + model_id）
- 测试时验证失败直接拒绝保存（422 + 详细错误），避免错误配置进入生产
- 运行时调用失败自动 fallback 到默认 `AUDIT_TEXT_MODEL`，保证生成流程不中断
- 运行时的 fallback 行为以弱提示（方案 B）形式在生成结果页面告知用户
- 新增模块复用现有基础设施（Fernet 加密、OpenAI SDK 客户端、probe 函数）
- 不影响现有 3-fixed-provider 模型路由的行为

**Non-Goals:**
- 不支持内容生成 (`generator.py` / `MAIN_WRITER_MODEL`) 使用自定义模型 — 生成环节对模型能力要求高，需要更严格的 provider 体系
- 不支持视觉审核 (`visual_auditor.py` / `VISUAL_AUDIT_MODEL`) 使用自定义模型 — 视觉审核是多模态能力，需要专门的 vision 模型，不在本变更范围内
- 不支持非 OpenAI 兼容协议（如 Anthropic Messages API、Google Generative AI API、Ollama）
- 不支持一个用户配置多个自定义审核模型 — 一个用户一行，简化 UI 和路由逻辑
- 不改动现有 provider registry 或 user-api-key billing 系统 — 避免对 200+ 行核心代码做破坏性改造
- 不支持审核模型的流式输出 — 审核是短文本判定，无需流式

## Decisions

### Decision 1: 独立数据模块 vs 扩展现有 provider registry

**选择**：新增独立的 `user_custom_audit_models` 表 + `core/custom_audit.py` 模块

**理由**：
- 现有 `model_providers` 表是为 N 个固定供应商设计的元数据表（含 pricing、capabilities、supported roles 等丰富字段），不是为 per-user 自定义设计
- 现有 `provider_credentials` 表是为 platform-user 双层凭证设计的，FK 到 `model_providers`，新增 per-user 自定义 provider 会破坏 schema 语义
- 审核模型配置是 per-user 私有数据，与平台级 provider registry 解耦更符合数据边界
- 独立模块只影响审核流程的单一调用点，变更风险可控

**替代方案考虑**：
- ❌ 在 `model_providers` 表加 `is_user_defined` 列 + `owner_user_id` 列：会污染现有 provider 查询语义，且影响 `provider_code_for_model()` 的名字前缀判定逻辑
- ❌ 完全重构 provider system 为 N-provider 动态注册：改动面 400+ 行，远超本变更范围

### Decision 2: 单卡单模型 vs 多卡多模型

**选择**：每用户一行配置记录

**理由**：
- 用户心智模型简单：审核模型 = 一种选择，不需要切换
- UI 简单：Settings 页一个卡片搞定
- 实现简单：CRUD 操作只有 insert / read / update / delete 4 种
- 覆盖 95% 场景：绝大多数用户只需要一种审核模型

**替代方案**：
- ❌ 多卡多模型 + 激活态下拉框：UI 复杂度高，增加 1 张表 (`user_custom_audit_model_choices`) + 1 个 API + 前端下拉组件，超出需求

### Decision 3: 测试策略 vs 运行时策略

**选择**：测试时**严格拒绝保存**，运行时**自动 fallback + 弱提示**

**理由**：
- **测试阶段是配置错误的最佳拦截点**：用户刚输完 base_url + api_key，立刻 probe，发现问题最自然；拒绝保存避免错误配置进入生产环境
- **运行时是生成流程的关键路径**：不能让一个坏配置卡住整个生成流程；fallback 到已知可用的默认模型是安全选择
- **弱提示 (方案 B) 是 UX 平衡点**：
  - ✅ 比静默 fallback 好：用户知道自己填的模型有问题，能及时修配置
  - ✅ 比强警告好：不破坏流程连续性，不引入邮箱打扰
  - ✅ 弱提示可被用户忽略（不阻塞结果查看），但不影响信息可见性

**替代方案考虑**：
- ❌ A 静默 fallback：用户无法感知配置失效，可能长期用默认模型浪费钱
- ❌ C 强警告 + Toast + 邮件：过度打扰，且邮件集成复杂
- ❌ 测试时宽松 + 运行时严格：错误配置进入生产，运行时直接失败中断生成

### Decision 4: Probe 验证逻辑

**选择**：复用 `core/api_key_validation.probe_api_key_model(api_key, model_id, base_url_override)`

**理由**：
- 现有 probe 已经发送 `{system: "Return OK.", user: "Reply with OK only."}` + `max_tokens=8` + `temperature=0`
- 任何 OpenAI 兼容模型都能响应这种最小请求
- 不需要额外实现一套验证逻辑
- 已有完善的错误分类逻辑（`core/provider_errors.classify_provider_error`）

**实现细节**：
- 在 `probe_api_key_model` 签名中新增可选参数 `base_url_override: str | None = None`
- `custom_audit` 模块调用时传入用户的 `base_url`
- 现有 3 个 provider 的 probe 调用保持不变（base_url_override = None，走原 `_base_url_for_provider()` 逻辑）

### Decision 5: Fallback 错误分类与通知粒度

**选择**：每次 audit 调用返回 `{verdict, issues, fallback_event?}` 结构，由生成流程聚合后一次性通知

**理由**：
- 一次生成可能有 N 个片段 × M 次 fallback，逐条 Toast 会淹没用户
- 聚合后在生成结果页的"运行概览"区域显示单次 banner，列出失败次数 + 模型名 + 错误摘要
- 每个 fallback_event 持久化到 session 的 events 表，便于后续追溯和故障定位

**数据结构**：
```
audit_fallback_events: list[{
    "segment_index": int,              # 哪个片段触发
    "custom_model_id": str,            # 用户自定义的 model_id
    "fallback_model_id": str,          # 实际用的默认模型
    "error_kind": "auth"|"network"|"timeout"|"rate_limit"|"bad_response",
    "error_detail": str,               # 错误摘要（不含 api key）
    "occurred_at": timestamp
}]
```

**前端 banner 渲染规则**：
- 仅在 `audit_fallback_events` 非空时显示
- 聚合显示：`自定义审核模型（{name}）本次有 {N} 次调用失败，已自动回退到默认 {model}。{首个错误摘要}`
- Banner 提供 "前往设置" 链接跳到 `/settings#custom-audit-model`

### Decision 6: 协议范围

**选择**：仅支持 OpenAI 兼容协议

**理由**：
- 国内 95% 的便宜模型（商汤/Moonshot/字节豆包/百川/MiniMax/智谱 GLM 等）都提供 OpenAI 兼容 endpoint
- 非兼容协议（Claude Messages API、Gemini API、Ollama）接入需要专门的 SDK adapter，成本远超收益
- 现有 `openai.OpenAI(api_key, base_url, timeout, max_retries)` 客户端已经封装好所有兼容协议的差异
- 未来如需扩展协议，可以基于 OpenSpec 开新 change（不阻塞本变更）

**拒绝的非 OpenAI 兼容协议示例**：
- ❌ Anthropic Messages API（`messages` 数组 + `system` 字段不在 `messages` 内）
- ❌ Google Generative AI（REST + 不同的 token count 计费）
- ❌ Ollama REST API（不支持 OpenAI SDK，需要 HTTP 直接调用）

### Decision 7: i18n 范围

**选择**：新增约 15 个 keys，覆盖 Settings 卡片区 + 生成结果 fallback banner

**理由**：
- 现有 i18n 已有 `login.registerHint` 等 800+ 个 keys，新增 ~2% 体量可控
- 自定义审核模型是独立功能区，不应混用现有 provider 文案
- 弱提示 banner 需要 3-4 个新的 keys 表达 "fallback occurred" / "前往设置" / "自定义模型名" / "默认模型名"

**新 keys 命名约定**：
- `settings.customAudit.title`, `.description`, `.namePlaceholder`, `.baseUrlPlaceholder`, `.modelIdPlaceholder`, `.apiKeyPlaceholder`, `.saveButton`, `.deleteButton`, `.validated`, `.failed`, `.testedAt`, `.runtimeHint`
- `generate.fallbackBanner.title`, `.body`, `.goToSettings`, `.defaultModel`

### Decision 8: 加密方案

**选择**：复用 `core/billing.py` 的 `encrypt_api_key()` / `decrypt_api_key()`

**理由**：
- 现有函数已经实现 Fernet + SHA256 双路径加密，支持密钥轮换
- 审核 api_key 的敏感度高（同 generation key），复用现有密钥管理避免引入新的安全风险
- 不需要额外设计 key 层级

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 用户配置错误的 base_url（如拼写错误）通过测试但运行时失败 | probe 已经验证 base_url 的连通性；运行时 fallback 保证生成不中断；弱提示 banner 让用户及时发现问题 |
| OpenAI 兼容协议的实现不完全一致（如缺少 `model` 字段、`usage` 字段缺失） | 现有 `probe_api_key_model` 和 `content_auditor` 的调用已对字段缺失做了容错处理；fallback 兜底 |
| Fernet 密钥泄露后，用户 api key 也泄露 | 复用现有 billing 加密路径，密钥轮换流程已存在；新增列与 provider_credentials 使用相同的加密列模式 |
| 默认审核模型本身挂了 | 现有 `AUDIT_TEXT_FALLBACK_MODEL` 链路 + 最终 fallback 到"跳过审核"已存在；本变更不改变此行为 |
| 用户 base_url 被用来做 SSRF 攻击（访问内网服务） | 需要新增 URL 格式校验（必须 http/https，禁止 `localhost`, `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`） |
| 新增模块破坏现有审核流程 | 所有审核调用点集中在 `content_auditor.py` 的 `_audit_segment()` 方法；新增逻辑封装在 `_resolve_audit_client()` 内，调用点零侵入 |
| 生成流程延迟增加 1 次 DB 查询 / 片段（查用户自定义配置） | 通过 user_id 索引查询 O(1)；首次查询后缓存在 auditor 实例内存（每生成 session 内复用），单次查询成本 < 1ms |

## Migration Plan

### Step 1: 数据库 migration (向后兼容)

1. `migrations/mysql/005_user_custom_audit_models.sql`:
   - `CREATE TABLE IF NOT EXISTS user_custom_audit_models (...)`
   - 仅新增表，不修改现有表，不破坏旧数据
2. SQLite inline DDL 同步添加（与 MySQL 表结构一致）
3. 新表初始为空，所有用户默认走原有 `AUDIT_TEXT_MODEL` 路径

### Step 2: 后端代码部署

1. 新增 `core/custom_audit.py`
2. 修改 `core/api_key_validation.py`：为 `probe_api_key_model` 增加 `base_url_override` 参数
3. 修改 `core/content_auditor.py`：新增 `_resolve_audit_client()` 方法，封装自定义模型解析逻辑
4. 修改 `server.py`：新增 3 个 endpoint
5. 所有改动向后兼容：
   - 用户没配自定义模型时 → 沿用原路径，零行为变化
   - 用户配了自定义模型时 → 走新路径，但 fallback 到默认

### Step 3: 前端部署

1. Settings 页面新增自定义审核模型卡片（独立组件，不影响现有 3 个 provider 卡）
2. 生成结果页面新增 fallback notification banner（独立组件，仅在有 fallback events 时渲染）
3. 新增 i18n keys（向后兼容，无 keys 时使用 fallback 默认值）

### Rollback Strategy

- **数据库**：`DROP TABLE user_custom_audit_models` 即可（新表无存量数据依赖）
- **后端**：revert 4 个文件的提交，`_resolve_audit_client()` 删除后即恢复到默认模型路径
- **前端**：revert Settings 卡片 + fallback banner 组件，i18n keys 保留即可（不破坏）

## Open Questions

（无。所有关键技术决策已在 Decisions 章节闭合。）
