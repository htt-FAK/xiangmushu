## Why

当前 Streamlit 应用打开后直接进入「知识库 / 模板 / 生成预览」三标签，新用户不清楚产品能做什么、推荐操作顺序，也不便于演示与验收时快速确认环境是否正常。增加一个轻量的 **Hello / 首页** 可降低上手成本，并为后续引导（模式说明、模型配置提示）提供固定入口。

## What Changes

- 在主界面增加 **「首页」** 标签（置于现有三标签之前），展示产品简介、推荐使用步骤与当前关键配置摘要（如是否已配置网关 Key、默认生成模式）。
- 首页提供跳转到「知识库管理」「模板配置」「生成预览」的简短指引，不要求用户必须先读完才能使用其它标签。
- 可选：在侧栏保留现有配置项不变；首页仅只读展示部分状态，不重复侧栏全部控件。
- 不改动核心生成、检索、回填流水线行为；无 **BREAKING** API 变更。

## Capabilities

### New Capabilities

- `hello-page`: 应用内欢迎/首页展示、使用步骤说明、环境与配置状态只读摘要，以及与现有三标签的导航关系。

### Modified Capabilities

<!-- 无既有 openspec/specs；不涉及既有 capability 的需求变更 -->

## Impact

- **代码**：`app.py`（标签页结构、首页 UI 区块）；可能抽取少量展示函数到 `core/` 或 `ui/` 模块（若保持 `app.py` 可读性）。
- **依赖**：无新 Python 依赖；继续使用 Streamlit。
- **配置**：读取现有 `config`（如 `chat_llm_configured()`、`embedding_llm_configured()`）用于首页状态提示，不新增必填环境变量。
- **文档/测试**：可在 `docs/测试与验收.md` 增加「打开应用可见首页」的冒烟项；与 OpenSpec 后续 `specs/hello-page/spec.md`、`design.md`、`tasks.md` 对齐实施。
