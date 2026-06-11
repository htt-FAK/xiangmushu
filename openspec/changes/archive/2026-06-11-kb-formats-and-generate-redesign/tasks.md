## 1. Python 依赖与项目配置

- [x] 1.1 在 `requirements.txt` 显式声明 `markitdown` 的 patch 版本依赖，并确认 `pip install -r requirements.txt` 后 `from markitdown import MarkItDown` 可以直接成功。

## 2. 知识库格式兜底：核心转换函数

- [x] 2.1 在 `core/kb_extract.py` 新增 `MARKITDOWN_FALLBACK_EXTS` 白名单常量与 `_convert_with_markitdown(path) -> str | None` 辅助函数（lazy `from markitdown import MarkItDown`，转换异常/空返回均返回 `None` 并 `logger.warning`）。
- [x] 2.2 在 `core/kb_extract.path_to_parsed_document()` 的现有扩展名分发之后、`raise ValueError` 之前新增白名单分支：命中时调用 `_convert_with_markitdown`，成功则复用 `_extract_markdown_blocks()` 输出 `kb_source_type="markdown"` 的 `ParsedDocument`；失败则 fall through 到现有 `ValueError("不支持的文件类型")`。

## 3. 上传路由扩展名预检

- [x] 3.1 新增 `core.kb_extract.is_supported_kb_extension(ext)`（汇总直接分支 + MarkItDown 白名单），供路由共享“支持/不支持”语义。
- [x] 3.2 在 `server.py` 的 `POST /api/kb/upload` 路由中，对每个上传文件先在落盘之前调用 `is_supported_kb_extension`；不支持时直接返回 `{ok: false, error, unsupported_format: true}`，不写盘、不记审计日志。

## 4. 知识库格式兜底：后端测试

- [x] 4.1 在 `test_kb_extract_markitdown_fallback.py`（新文件）里为 `.txt / .csv / .html / .htm / .xlsx / .xls / .doc` 各写一条 happy path 单测（可用 fixture 文件），断言 `ParsedDocument.kb_source_type="markdown"`、有非空 text。
- [x] 4.2 新增一条“未知扩展名走兜底失败”的单测，断言抛 `ValueError`，并断言 `is_supported_kb_extension(ext)` 为 False。
- [x] 4.3 新增一条“未知扩展名上传”接口测试，断言 HTTP 错误响应包含 `unsupported_format=true` 且 `data/historical/` 下未产生文件。

## 5. 生成仓主页：极小化预览 / Banner

- [x] 5.1 在 `frontend/src/pages/GeneratePage.tsx` 替换现有“实时内容”面板：不再 inline 调用 `renderOutputBlocks(true)`；当 `outputs.length === 0` 沿用 `EmptyState`，否则渲染单行 Banner。
- [x] 5.2 Banner 在 `running=true && outputs.length > 0` 时展示 i18n `generate.streamingStatus(progress.done, progress.total)` 与“查看当前进度 →”按钮，按钮统一调用 `setTraceOpen(true)`。
- [x] 5.3 Banner 在 `running=false && outputs.length > 0` 时展示 i18n `generate.completedSummary(outputs.length) + generate.viewFullTrace`，按钮同样打开 trace 抽屉。
- [x] 5.4 在 `frontend/src/components/OutputBlock.tsx` 为抽屉内的 regenerate 状态增加一个可选 `busyLabel` 兼容现有 `regenerating` 文案（复用已有 `busy`/`busyLabel` 属性即可，不需要新增属性）。

## 6. 重新生成交互收束到 trace 抽屉

- [x] 6.1 在 `GeneratePage` 把“查看生成过程 / Trace”抽屉从“仅在 `downloadPath && !running` 时可见”改为任何 `outputs.length > 0` 时均可触发，使 Banner 按钮可以正常工作。
- [x] 6.2 把抽屉内的 `renderOutputBlocks(false)` 改为 `renderOutputBlocks(true)`，让抽屉内每个 OutputBlock 都带 regenerate 按钮；主页不再渲染 `renderOutputBlocks(true)`（已由 5.1 完成）。
- [x] 6.3 确认抽屉关闭后，主页 Banner 的“已完成 N 个章节”会按最新 `outputs.length` 反映，`regeneratingIndex` 不为 `null` 时 Banner 同步显示 `generate.regenerating` 文本（用现有 `busy` 状态派生即可）。

## 7. 运行状态区：紧凑 Token 摘要与底部费用板块

- [x] 7.1 删除 `GeneratePage.tsx` 中原“费用与 Token”板块（对应 `generate.billingTitle` / `generate.inputTokens` / `generate.outputTokens` / `generate.totalCost` 渲染区域）。
- [x] 7.2 在 run-overview `Stat` 行的正下方新增一行紧凑文案 `generate.tokenSummaryLine(runBilling.input_tokens, runBilling.output_tokens)`；当 `runBilling` 为 null 时不渲染或显示 “—”。
- [x] 7.3 保留原有 run-overview 中的 `generate.runCost` Stat（已有、无需改动）；删除所有 `billingSummary` 在生成页的渲染与读取（相关 `fetchBillingSummary` 调用如不再被其它地方消费可一并清理）。

## 8. 生成仓：显式控制开关

- [x] 8.1 把 `GeneratePage` 中的 `enableWeb / enableAudit / enableVisualAudit` 升级为可变 state（`useState` + 对应 setter）；`useStream` 保持常量 `true`。
- [x] 8.2 在“生成质量”三档选择器下方新增一组三个开关 UI（建议直接在页面内实现内联 `ToggleSwitch` 组件，使用 `ui.tsx` 既有的按钮样式语言），标签复用 `generate.enableWeb / generate.enableAudit / generate.enableVisualAudit` 及对应 `*Desc`。
- [x] 8.3 引入 `userOverrodeSwitchesRef`：用户首次手动切换开关时置 true；`recommendedConfig` 变化时仅在 `!userOverrodeSwitchesRef && !busy` 情况下同步初始默认值，避免覆盖用户显式选择。
- [x] 8.4 在 `busy=true` 时把三个开关 UI 标记为 disabled，与 `qualityMode` 选择器、文本域、知识库/模板 rail 的 disabled 行为保持一致。

## 9. 前端文案（i18n）

- [x] 9.1 修改 `frontend/src/i18n.ts` 的 `knowledge.uploadHint`（zh + en）：列出新支持的格式范围，并说明“部分格式会先转为 Markdown 文本再入库”；新增 `knowledge.unsupportedFormat` 文案用于路由预检失败的报错展示。
- [x] 9.2 在 `i18n.ts` 的 zh/en 区块内分别新增 `generate.streamingStatus`、`generate.completedSummary`、`generate.viewFullTrace`、`generate.viewLiveProgress`、`generate.tokenSummaryLine` 五条文案（按现有占位符约定格式化）。
- [x] 9.3 确认 `generate.enableWeb / generate.enableAudit / generate.enableVisualAudit` 与对应 `*Desc` 在 zh/en 中均已存在且含义与新开关 UI 一致，必要时微调措辞而不修改 key。

## 10. 回归与验收

- [x] 10.1 运行 `pytest test_kb_extract_markitdown_fallback.py test_billing_user_apikey.py test_manual_functional_flow.py -q`，全部通过。
- [x] 10.2 在 `frontend/` 下运行 `npm run build`，TypeScript 与 Vite 构建均通过。
- [x] 10.3 手工验收：知识库页上传 `.txt / .html / .xlsx` 文件能成功入库并出现在来源列表；上传 `.zip` 等白名单外格式能拿到明确错误且不落盘。
- [x] 10.4 手工验收：生成页主页无 OutputBlock 列表；生成中 Banner 显示“AI 正在生成第 X/Y 节 ▮”；生成完成 Banner 显示“已完成 N 个章节 · 查看完整生成过程 →”；点击按钮能打开抽屉；抽屉内的 regenerate 能正常工作；主页不再显示底部费用板块，run-overview 出现紧凑 Token 行；三个开关初始态符合 smart defaults、用户切换后不会被覆盖、生成中 disabled。
