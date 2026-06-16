## Context

项目计划书生成器是一个基于多段落生成、联网补料与文档填充的多模态 AI 智能体应用。系统提供流式 SSE 事件推送。
但在生产和开发中，该系统遇到了一些由于**事件同步缺陷、数据库异常吞没、交互锁定失效以及中英混合未国际化**引发的痛点 Bug，导致生成进度卡死（固定在最后一个章节）、审核误报、用户大模型配置失效、已生成面板交互数据蹦极、以及历史记录英文报错等。

## Goals / Non-Goals

### Goals
1. **进度精确同步**：重构 `server.py` 的事件推送逻辑。只在任务线程真正开始处理对应 index 的段落时，才推送 `"task"` 事件，避免启动瞬间被 122 个事件淹没导致状态停留于 `"6.3 未来展望 0/122"`。
2. **彻底隔离审计步骤**：在关闭审核开关（`enable_audit=False`）时，本地 `rule_audit` 规则校验虽运行，但不触发 `"audit"` 状态迁移（不改变全局 `current_step` 为 `"audit"`），解决前端误显示“审核Agent”的 UI 歧义。
3. **数据库故障与自定义模型故障显式告警**：重构大模型偏好与设置中心的异常处理。如连接 MySQL 失败或数据库处于降级态，不在 Resolve 层静默 `pass`，而是将详细的数据库连接失败作为 `warnings` 连带返回给前端 Settings 页面显示。
4. **生成完成后锁定交互面板**：生成结束（`done` / `error` / `terminated`）后，死锁或禁用生成页面的配置项（包括 Quality Mode 与 customInstructions），使 `RunOverview` 与已经生成的历史特征绑定，不随用户随后的鼠标点击点击重新切换。
5. **历史记录健壮性与归档处理**：确保历史记录保存（`persist_session_snapshot`）失败时只记录日志但不阻断生成进程，并在前端将所有未连接状态作为友好中文提示。
6. **全中文国际化清理**：翻译 `HistoryPage`、`TemplateAnalysisPage`、`KnowledgeBasePage` 中的英文硬编码及默认报错 Fallback 字符，确保系统在中文状态下不出现纯英文提示。

### Non-Goals
- 不修改大语言模型的实质生成 Prompt 和 RAG 底层算法。
- 不引入新的外部数据库或底层第三方库。

## Decisions

### 1. 事件推送流式精确化
- **现状**：生成任务开始时，一次性瞬间发出 122 个 `{"type": "task", ...}` 事件。由于最后发出的事件是 `index=121`（第六章最后节），前端直接将 active 状态更新为了该任务名称，从而造成进度永远卡在 `"正在生成: 6.3 未来展望 (0/122)"`。
- **决定**：取消开始前的虚假批量事件推送。把 `"task"` 事件的 `emit` 动作直接移入 `_generate_one_task` 的子线程执行逻辑起点，使其在执行到该任务时才实时向 SSE 通道发送事件。

### 2. 静态审计不阻塞 Generation 步骤状态
- **现状**：即使 `enable_audit` 为 `False`，若本地静态规则正则匹配到字数超限、Markdown 符号或前缀问题，依然触发 `"type": "audit"` 事件，让前端强制进入 `step = "audit"`。
- **决定**：在 `"audit"` 类型的事件中增加 `"is_model_audit"` 标志。只有在 `local_auditor is not None` 时，该标志才为 `True`。前端和后端 Session 处理器只有在 `"is_model_audit": true` 时才将 `current_step` 更新为 `"audit"`。对于本地正则提示，仍更新 Block 的 auditIssues 以供展示警告，但全局不进入 Audit Step 步骤。

### 3. 自定义大模型降级显式返回 warnings
- **现状**：`core/provider_registry.py` 中 `load_user_model_choices` 出错时被吞掉，导致大模型设置失效且用户不知情。
- **决定**：
  - 在 `get_user_preferences` 中捕获 MySQL 异常。如果 MySQL 连接失败，回滚至内存和空配置并返回含有中文说明的 `warnings`（如 `{"database": "数据库连接异常，暂自动降级为系统默认模型"}`）。
  - 前端 Settings 页面将正确捕获这些 warnings 并将其以黄色警告框友好地呈现在大模型选择项下方，而不再是空白色或无故回滚。

### 4. 前端在生成结束后禁用 QualityMode 更改
- **现状**：生成结束后，`SetupPanel` 的 QualityMode 重获点击权，点击后由于全局 state 变化，`RunOverview` 的“当时生成模式”也随之跳转。
- **决定**：在 `SetupPanel` 中，将配置项（包括 Quality Mode 下的选择框）的 `disabled` 状态判定更新为 `disabled={busy || outputs.length > 0}` 或 `disabled={running || outputs.length > 0}`，在生成已经产出过 Block 后完全锁定，只有点击“重新生成”（Regenerate / Reset）时才重新解禁。

### 5. 中文本地化国际化覆盖
- **HistoryPage**:
  - 将硬编码的 `"Backend unavailable"` 翻译为 `"后端服务未连接"`。
  - 将 `"Loading history..."` 翻译为 `"正在加载历史记录..."`。
  - 将 `"No records match the current filters."` 翻译为 `"没有符合当前筛选条件的历史记录。"`。
  - 将 `"History records are not available right now."` 翻译为 `"当前无法获取历史记录。"`。
  - 将 `"Waiting for history data..."` 翻译为 `"等待历史记录数据..."`。
  - 将 `"No selectable record while history is unavailable."` 翻译为 `"暂无可选的历史记录。"`。
  - 将 `tokens` 单位显示转为 `" 字符 (Tokens)"`。
- **TemplateAnalysisPage**:
  - 将 Stat 的英文 labels 翻译为 `"输入 Tokens"`, `"输出 Tokens"`, `"费用 (元)"`。
  - 将 属性面板中的标签 `"Vision model"`, `"Planner model"`, `"Phase"`, `"Status"` 分别翻译为 `"视觉模型"`, `"规划模型"`, `"分析阶段"`, `"分析状态"`。
  - 替换 `normalizeErrorMessage` 传参中的 `"Failed to load templates."` 等英文硬编码字符串为语义对应的中文。

## Risks / Trade-offs

- **[Risk]** 多线程下进度可能非顺序更新 → **[Mitigation]** 前端 Progress 已采用 `{done: x, total: y}` 的比值渲染模式，且段落列表在 Trace 抽屉中是按固定 index 排好序展示的。这有助于更直观地体现并发并行的优势，同时当前任务标题（`currentTask`）会自动显示最先到达/或正在并发推进的段落名称，体验更好。
