## Context

仓库当前存在两类并行的体验割裂：

1. **知识库入库格式面窄**。`core/kb_extract.path_to_parsed_document()` 只分发 `.docx / .pdf / .pptx / 图片 / .md(.markdown)`，对其它扩展名直接 `raise ValueError("不支持的文件类型: {ext}")`。`MarkItDown` 在仓库里已被使用但仅作为 PDF 的可选增强（lazy import，无 requirements 声明），并未被作为“格式兜底转换器”使用。

2. **生成仓主体布局失控**。“实时内容”面板把所有 OutputBlock 平铺到主页，没有边界也没有折叠，把后续的“验收”与“审核信号”推到很远；而底部“费用与 Token”板块与顶部“run-overview”里的 `runCost` 重复，且页面整体信息密度不均衡。

3. **开关 UI 与后端能力脱钩**。`GeneratePage` 里 `enableWeb / enableAudit / enableVisualAudit / useStream` 都是 `useState(false|true|true|true)` 的只读常量（没有 `setX` 绑定）。i18n 里这些开关的文案（`generate.enableWeb*`、`generate.enableAudit*`、`generate.enableVisualAudit*`、`generate.simpleMode / advancedMode`）都还在，说明是 React 重写时未把老 UI 接回来。

约束与干系人：
- 后端是 Python 3.10+ 的 FastAPI 单进程；不引入 Celery/Redis 等基础设施。
- 前端是 React + Vite；不新增 UI 框架，仅在现有 `components/ui.tsx` 风格基础上扩展。
- 干系人：最终用户（上传资料、启动生成、审阅结果），与仓库已有的“生成会话 + 工作流状态 + 强校验 API Key”能力保持兼容。

## Goals / Non-Goals

**Goals:**
- 让 `.txt / .csv / .html(.htm) / .xlsx / .xls / .doc` 等常见资料文件能通过统一管线进入知识库，复用现有 Markdown 切块/入库链路。
- 把“生成仓主页面”重塑为极简状态预览：生成中仅显示 `AI 正在生成第 X/Y 节 ▮`，完成后仅保留摘要与“查看完整过程”入口；全部 OutputBlock 与重新生成交互统一迁入 trace 全屏抽屉。
- 删除底部“费用与 Token”板块；把输入/输出 Token 摘要搬到顶部 run-overview 的一行紧凑位置。累计成本保留在管理员面板与设置面板。
- 显式恢复三个操作开关：`联网补充 / 内容审核 / 视觉审核`；流式输出保持默认开启，不暴露；初始值沿用 `recommendedConfig` 的 smart defaults，用户可显式覆盖。
- 调整上传提示文案，如实反映新支持的格式范围并说明“部分格式会先转为 Markdown 再入库”。

**Non-Goals:**
- 不为每种新格式写独立 parser（坚持走 MarkItDown 兜底 → Markdown 切块统一路径）。
- 不做“任何未知扩展名都尝试 MarkItDown”的开放兜底，避免二进制/加密/压缩包等不可解析文件被错误落盘。
- 不引入任务队列、后台 worker 或额外的持久化。
- 不调整生成会话（session recovery）、API Key 强校验、首页引导清单、favicon 等前序已交付的能力。
- 不为 XLSX/DOC 等转换质量不佳的格式做“保版式”保证；明确告知用户会丢版式信息、以文本为主。
- 不引入新的 `Collapse / Accordion / Disclosure` 公共组件；仅为本页所需内联实现极简展开态（trace 抽屉已有，复用即可）。

## Decisions

### Decision 1：KB 格式兜底走 MarkItDown，但用“显式白名单”控制范围

在 `core/kb_extract.py` 里新增辅助函数 `_convert_with_markitdown(path) -> str | None`，返回转换后的文本；在 `path_to_parsed_document()` 的扩展名分发之前，按下列白名单走兜底：

```text
MARKITDOWN_FALLBACK_EXTS = {
  ".txt", ".csv", ".html", ".htm",
  ".xlsx", ".xls", ".doc",
}
```

白名单命中后调用 `MarkItDown().convert(path).text_content`，把结果视作 Markdown 文本并走已有的 `_extract_markdown_blocks()` 路径；转换失败才 fall through 到已有的 `raise ValueError(...)` 分支。

> 为什么是白名单而不是“任何未知格式都试”：`MarkItDown.convert()` 对二进制、加密 Office、复杂 ZIP 等会抛错或空返回；不加限制会造成不可解析的文件先被落盘到 `data/historical/`，再失败时既无清理也无稳定错误语义。白名单让失败路径可预测、可测试。

备选方案：
- 在 `requirements.txt` 里不声明 `markitdown`，仅靠用户手工安装。→ 放弃，仓库已经在 PDF 分支里 lazy import 它，等于把它作为事实依赖但没有契约。
- 每种格式各写一个 parser。→ 放弃，XLSX 与 DOC 的复杂表格/样式难以做到比 MarkItDown 兜底更好，且维护成本高。

### Decision 2：PDF 分支保持 “MarkItDown first + pypdf fallback” 不变

`_extract_pdf_blocks()` 已经是 MarkItDown 优先、pypdf 兜底的结构（`core/kb_extract.py:43-105`）。本次不改动该分支；新增的 `_convert_with_markitdown()` 只是把它背后的“MarkItDown 可用就拿来兜底”语义，从 PDF 扩展到白名单里的其它格式。

> 为什么：PDF 已有稳定 fallback，且其输出已经被 PDF 专用切块代码消费；其它格式（xlsx/doc 等）没有专用 parser，正好适合走统一的“转 Markdown 再切块”路径。

### Decision 3：`requirements.txt` 显式声明 `markitdown`

把 `markitdown>=X.Y` 写进 `requirements.txt`（版本号按当时最新稳定版固定到 patch），不再依赖开发者手工安装。

> 为什么：PDF 分支其实已经以 lazy import 形式依赖它，等于“隐式可选依赖”；显式化后部署与测试都更稳定，且 `scripts/benchmark_pdf_parser.py` 也能直接跑通。

备选方案：
- 保留可选、加 `requirements-optional.txt`。→ 放弃，多一个依赖文件在团队协作里更容易失同步。

### Decision 4：上传路由加扩展名预检，先拒绝再落盘

`server.py:POST /api/kb/upload` 当前在调用 `path_to_parsed_document()` 之前已经 `with open(save_path, "wb")` 写盘。本次增加：
- 一个“扩展名是否被支持”的预检函数（白名单 = 直接分支 + MarkItDown 兜底分支）。
- 不支持时直接返回 400 错误、不落盘、不写审计日志。

> 为什么：减少“先落盘再失败”的脏文件堆积；错误响应更精确，便于前端文案定位（“不支持该格式，请上传 PDF/DOCX/TXT/...”）。

### Decision 5：生成主页替换为极小化“AI 思考中”流式条

`GeneratePage` 主右栏当前是：

```text
run-overview → outputTitle(全量 OutputBlock) → acceptance → audit → billing
```

调整为：

```text
run-overview(+紧凑 Token 行) → minimal-stream-banner → acceptance → audit (trace 抽屉承载全量 OutputBlock 与 regenerate)
```

Minimal stream banner 行为：
- `running=true` 且 `outputs.length > 0`：显示一行 `AI 正在生成第 {progress.done}/{progress.total} 节 ▮`，带 `查看当前进度 →` 按钮。
- `running=false` 且 `outputs.length > 0`：显示一行 `已完成 {outputs.length} 个章节 · 查看完整生成过程 →`。
- `outputs.length === 0`：沿用现有 `EmptyState`。

点击“查看”按钮打开 trace 全屏抽屉（同一份 `renderOutputBlocks(false)`，但加上 `regenerate` 操作）。

> 为什么：这是用户拍板的最激进方案，能最大程度把“验收/审核”板块拉回视口；所有细节交给 trace 承载，避免双 UI 同步。

备选方案：
- 限高滚动预览 + expand。→ 用户已否。
- 当前列表只加限高。→ 用户已否。

### Decision 6：`regenerate` 入口统一收进 trace 抽屉

主页只保留 Banner，不再渲染 `<OutputBlock />` 列表；`regenerate` 按钮仅出现在 trace 抽屉里的 `renderOutputBlocks(true)` 渲染。

> 为什么：与方案 5 一致的最激进方案配套；避免“主页看到片段但改不动”的反差体验，所有可操作章节都在抽屉内完成。

### Decision 7：紧凑 Token 行搬到 run-overview

保留的底部“费用与 Token”板块移除；在 run-overview `Stat` 行的下方加一行紧凑文案：

```text
本会话：输入 {input} tokens · 输出 {output} tokens
```

`runCost` 已在 run-overview Stat 行内展示，重复项不保留；累计成本 `billingSummary.cost_cny + generation_count` 不在生成页露出，由管理员面板 + 设置页面承接。

> 为什么：保留“单会话”维度的可见性，避免底部板块与顶部重复；累计成本属于账号维度，不属于本会话。

### Decision 8：三个开关 UI 放在“生成质量”之下，作为显式控件

把 `enableWeb / enableAudit / enableVisualAudit` 升级成可变 state（`useState + setX`）；在 `qualityMode` 下方加一组三个 Switch（沿用 `ui.tsx` 已有按钮样式，新增一个极简 `ToggleSwitch` 内联实现即可）。

初始值来自 `recommendedConfig`：`enableWeb=!hasRichKB`、`enableAudit=isComplex`、`enableVisualAudit=true`（沿用现有常量）；用户一旦手动切换后，由 state 接管。

`useStream` 保持恒为 `true`，不暴露。

> 为什么：用户拍板“方案 A：3 个简单开关，直观、改动小”。smart defaults 仅作为初始值，避免覆盖用户显式选择。

备选方案：
- 简洁/高级模式两档。→ 用户已否。
- smart defaults + “调整”按钮折叠。→ 用户已否。

### Decision 9：i18n 文案统一调整

- 修改：`knowledge.uploadHint`（zh/en）反映新支持的格式列表 + “部分格式会先转为 Markdown 文本”。
- 新增：
  - `generate.streamingStatus`：`AI 正在生成第 {0}/{1} 节 ▮`
  - `generate.completedSummary`：`已完成 {0} 个章节`
  - `generate.viewFullTrace`：`查看完整生成过程`
  - `generate.viewLiveProgress`：`查看当前进度`
  - `generate.tokenSummaryLine`：`本会话：输入 {0} tokens · 输出 {1} tokens`
- 新增开关标签复用现有 `generate.enableWeb / generate.enableAudit / generate.enableVisualAudit` 与对应 `*Desc`；**不再**使用 `generate.simpleMode / generate.advancedMode`（保留 key 但本轮不复用）。

### Decision 10：不引入公共 Collapse/Disclosure 组件

`OptionRail` 已经有 `max-h-52/64 + overflow-y-auto` 的限高滚动范式可以复用；trace 全屏抽屉 (`fixed inset-0 z-50`) 已实现；本轮不需要抽象新组件。

## Risks / Trade-offs

- **[风险] MarkItDown 转换质量不稳定，特别是 XLSX 复杂表格与 .doc 旧格式** → 缓解：文档与上传提示明确“部分格式会先转为 Markdown 文本再入库，复杂版式可能丢失少量格式信息”；在 `kb_extract` 里对空返回文本做友好兜底文案；为转换函数加单测覆盖每种扩展名的 happy path。
- **[风险] `_convert_with_markitdown()` 异常路径被吞，导致“上传成功但 chunks 为空”** → 缓解：返回 `None` 时调用方回退到 `ValueError(不支持的文件类型: ...)`；同时记录 `logger.warning`；测试里覆盖“MarkItDown 抛错 → 用户看到明确报错”。
- **[风险] 上传路由预检拒绝后，前端仍可能显示“0 chunks”误导** → 缓解：后端响应 `{ok: false, error, unsupported_format: true}`，前端据此展示 i18n 的 `knowledge.unsupportedFormat` 文案。
- **[风险] trace 抽屉承载所有 OutputBlock 与 regenerate，抽屉关闭时用户难以发现“某节已重新生成”** → 缓解：抽屉内的 `setOutputs` 与主页共用同一份 state，重新生成完后主页 Banner 的“已完成 N 个章节”会按最新 `outputs` 长度更新，且 `regenerate` 时主页 Banner 同步显示 `regenerating...` 状态。
- **[风险] 三个开关接入后，`recommendedConfig` 每次 template/slug 变化都会重置用户选择** → 缓解：仅在 `!busy && (slug 或 template 变化)` 且用户**本次未手动切换过**时才同步 smart defaults；一旦用户切换过任一开关，`recommendedConfig` 不再覆盖 state。
- **[风险] 删除底部费用板块后，部分历史截图/文档与实际界面不符** → 缓解：本仓库 docs 目录若引用旧截图随后续验收文档更新；不在本次范围内。

## Open Questions

（无。用户在拍板阶段已逐项选定：方案 B、方案 B、选项 a、选项 b、选项 A。本设计文档对应固化。）
