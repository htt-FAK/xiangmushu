## Context

Streamlit 单页应用 `app.py` 使用 `st.tabs` 组织「知识库 / 模板 / 生成」；侧栏承载配置。无独立路由或多页框架。OpenSpec 变更仅增加欢迎层，不触碰 `core/` 生成链路。

## Goals / Non-Goals

**Goals:**

- 在 `app.py` 增加「首页」标签及 `_render_hello_tab()`，集中展示简介、步骤、只读状态。
- 复用 `config.embedding_llm_configured()`、`config.chat_llm_configured()`、`load_registry()`、现有 session key `generation_mode` / `SS_ACTIVE_KB`。

**Non-Goals:**

- 不新建 Python 包或 Streamlit multipage 目录。
- 不在首页重复侧栏表单控件。
- 不修改模型路由、Chroma、审核逻辑。

## Decisions

1. **实现位置：内联 `app.py` 函数**  
   页面内容约 40–60 行，抽离到 `core/` 收益低；与现有 `_render_*` 模式一致。

2. **标签顺序**  
   `st.tabs(["首页", "知识库管理", "模板配置", "生成预览"])`，首页为默认选中（Streamlit 默认第一个 tab）。

3. **移除主区重复 `st.info` 推荐条**  
   步骤说明迁入首页，避免与首页内容重复；侧栏「知识库管理」expander 仍保留 Key 提示。

4. **状态展示**  
   使用 `st.metric` / `st.success` / `st.warning` 展示 Key、当前库 slug、生成强度；模型 ID 用 `st.caption` 一行摘要（与侧栏 caption 一致即可）。

## Risks / Trade-offs

- **[Risk] 首页与侧栏文案重复** → 首页只保留摘要，详细参数仍在侧栏。  
- **[Risk] 用户忽略首页** → 其它标签行为不变，无强制门禁。

## Migration Plan

部署：拉代码后 `streamlit run app.py`，无需迁移数据。回滚：删除首页 tab 与 `_render_hello_tab` 即可。

## Open Questions

无。
