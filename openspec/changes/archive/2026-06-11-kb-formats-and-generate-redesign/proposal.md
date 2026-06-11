## Why

知识库入库只支持 `docx / pdf / pptx / 图片 / md`，用户常见的 txt、csv、html、xlsx、doc 等格式进不来；同时生成仓页面的「实时内容」区域把每段 OutputBlock 全部平铺在主页面，把验收、审核等关键板块推到很远的位置，且「联网补充、内容审核、视觉审核」三个开关被硬编码为只读常量，用户无法按需控制。

## What Changes

- 扩展知识库入库格式白名单，新增 `txt / csv / html / htm / xlsx / xls / doc`；对不直接支持解析的格式，统一走 `MarkItDown` 先转成 Markdown，再复用现有 Markdown 切块器入库。
- 重构生成仓主页面布局：把「实时内容」换成极小化的流式抽象（生成中仅显示 `AI 正在生成第 X/Y 节 ▮`，完成后显示 `已完成 N 个章节 · 查看完整过程 →`），所有 OutputBlock 与重新生成交互统一移入 trace 全屏抽屉。
- 移除底部的「费用与 Token」板块，将输入/输出 Token 摘要以紧凑的一行形式搬到顶部运行状态区；累计费用与生成次数保留在管理员面板与设置面板。
- 在「生成质量」下方恢复并暴露三个操作开关：`联网补充`、`内容审核`、`视觉审核`；流式输出保持默认开启且不暴露。三个开关的默认值沿用现有 `recommendedConfig` 的 smart defaults 行为，但用户可显式切换。
- 调整上传提示文案，如实反映新支持的格式范围，并说明“部分格式会先转为 Markdown 文本再入库”。

## Capabilities

### New Capabilities

- `kb-broad-format-support`：基于 MarkItDown 兜底的知识库扩展格式入库能力（txt / csv / html / htm / xlsx / xls / doc）。
- `generate-minimal-preview`：生成仓主页面的极小化实时内容预览与状态展示，配合 trace 抽屉承载完整 OutputBlock 与重新生成交互。
- `generate-control-switches`：生成仓显式暴露联网补充、内容审核、视觉审核三个开关，并复用 smart defaults 作为初始状态。

### Modified Capabilities

（无：本变更不需要修改 `openspec/specs/` 下已有规范。）

## Impact

- 后端：`core/kb_extract.py`（新增 MarkItDown 兜底分支与辅助函数），`requirements.txt`（声明 `markitdown` 依赖），必要时在 `server.py` 上传路由增加扩展名预检与磁盘落盘前的拒绝策略。
- 前端：`frontend/src/pages/GeneratePage.tsx` 主页面布局大幅调整，“实时内容”区域改造；底部费用板块移除，run-overview 新增紧凑 Token 行；新增三个开关 UI 接入到 `enableWeb / enableAudit / enableVisualAudit` state；`frontend/src/components/OutputBlock.tsx` 与 trace 抽屉承载完整 OutputBlock 与 regenerate 按钮；`frontend/src/i18n.ts` 新增/修改中英文文案（上传格式提示、极小化预览、开关文案、Token 摘要等）。
- 依赖：新增 Python 依赖 `markitdown>=X.Y` 用于格式转换。
- API：不引入新接口；现有 `POST /api/kb/upload` 与 `POST /api/generate` 等接口的请求参数保持不变，但上传错误返回更精确的格式支持提示；`enableWeb / enableAudit / enableVisualAudit` 在前端生效后的语义不变。
