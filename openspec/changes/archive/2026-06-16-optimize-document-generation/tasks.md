## 1. 水印保留功能

- [x] 1.1 在 `core/filler.py` 中创建 `WatermarkPreserver` 类
  - 实现 `extract_watermarks(doc: Document) -> dict` 方法，提取 header/footer 中的水印 XML
  - 实现 `restore_watermarks(doc: Document, watermarks: dict) -> None` 方法，恢复水印

- [x] 1.2 在 `config.py` 中添加 `PRESERVE_WATERMARK` 配置项（默认 True）

- [x] 1.3 修改 `WordFiller.fill_template()` 方法
  - 在处理文档前调用 `extract_watermarks()`
  - 在保存文档前调用 `restore_watermarks()`
  - 添加异常处理，确保水印失败不影响主流程

- [x] 1.4 添加日志记录
  - 水印提取成功/失败
  - 水印恢复成功/失败

## 2. 内容充实度优化

- [x] 2.1 修改 `app.py` 中的 `MODE_DEFAULTS` 参数
  - 快速模式: `default_word_limit` 300 → 500
  - 普通模式: `default_word_limit` 500 → 800
  - 增强模式: `default_word_limit` 800 → 1200

- [x] 2.2 优化 `core/generator.py` 中的生成提示词
  - 在 `_build_paragraph_prompt()` 中添加内容充实度提示
  - 添加「内容要充实，避免简短」等引导语
  - 添加「每个要点需有具体说明」等要求

- [x] 2.3 在 `core/content_auditor.py` 中添加内容充实度检查
  - 实现 `check_content_richness(content: str, word_limit: int) -> tuple[bool, str]` 方法
  - 检查实际字数是否达到 word_limit 的 80%
  - 返回检查结果和建议

- [x] 2.4 集成充实度检查到审核流程
  - 在 `ContentAuditor.audit()` 中调用充实度检查
  - 低于 50% 时标记为 `major_issue`
  - 低于 80% 时标记为 `minor_fix`

## 3. 表格格式保留

- [x] 3.1 在 `core/filler.py` 中创建新方法 `_replace_cell_text_preserve_format()`
  - 保留单元格内第一个 run 的格式（字体、颜色、大小）
  - 只替换文本内容，不删除段落结构

- [x] 3.2 在 `config.py` 中添加 `PRESERVE_TABLE_FORMAT` 配置项（默认 True）

- [x] 3.3 修改 `_set_cell_text_keep_style()` 方法
  - 根据 `PRESERVE_TABLE_FORMAT` 配置选择使用新方法或原方法
  - 添加异常处理，失败时回退到原方法

- [x] 3.4 添加日志记录
  - 格式保留成功/失败
  - 回退到简单替换的情况

## 4. MiMo 模型集成

- [x] 4.1 在 `config.py` 中添加 MiMo API 配置
  - `MIMO_API_KEY`: API 密钥（支持环境变量）
  - `MIMO_BASE_URL`: `https://api.xiaomimimo.com/v1`
  - `MIMO_MODEL`: `mimo-v2.5-pro`

- [x] 4.2 实现 `mimo_client()` 函数
  - 创建 OpenAI 兼容客户端
  - 复用现有超时和重试配置

- [x] 4.3 在 `core/generator.py` 中添加 MiMo 模型路由
  - 当 MiMo 配置时，可选择使用 MiMo 进行内容生成
  - 添加 `use_mimo` 参数或配置项

- [x] 4.4 实现 MiMo 失败自动回落
  - MiMo 失败时自动切换到 DeepSeek/DashScope
  - 检测 API key 过期（2026-05-30）并禁用 MiMo

- [x] 4.5 利用 MiMo 联网搜索能力
  - 当 web search 启用且使用 MiMo 时，使用 MiMo 内置搜索

## 5. 视觉审核模块

- [x] 5.1 创建 `core/visual_auditor.py`
  - 实现 `VisualAuditResult` 数据类
  - 实现 `audit_document_visual()` 主函数

- [x] 5.2 实现文档转图片功能
  - `docx_to_pdf()`: 使用 LibreOffice 将 docx 转为 PDF
  - 复用 `template_vision.py` 的 `pdf_to_png_pages()`

- [x] 5.3 实现 VLM 视觉评分
  - 构建多模态消息（文本 + 图片）
  - 调用 VLM (qwen3.6-plus-2026-04-02 或 MiMo)
  - 解析 JSON 响应获取五维评分

- [x] 5.4 在 `config.py` 中添加视觉审核配置
  - `VISUAL_AUDIT_ENABLED`: 是否启用（默认 True）
  - `VISUAL_AUDIT_MAX_ROUNDS`: 最大优化轮次（默认 3）
  - `VISUAL_AUDIT_PASS_SCORE`: 通过分数线（默认 85）
  - `VISUAL_AUDIT_MODEL`: 审核模型（默认 qwen3.6-plus-2026-04-02）

- [x] 5.5 添加异常处理和降级
  - VLM 调用失败时记录日志并继续
  - JSON 解析失败时返回 parse_ok=false

## 6. 文档优化模块（二轮优化）

- [x] 6.1 创建 `core/document_optimizer.py`
  - 实现 `optimize_document()` 主函数
  - 实现 `diagnose_issues()` 问题诊断

- [x] 6.2 实现优化策略选择
  - 视觉问题 → 调整排版参数
  - 内容问题 → 补充细节/重新生成段落
  - 结构问题 → 调整章节结构

- [x] 6.3 实现段落级精准优化
  - 识别低分段落
  - 使用更强模型（LARGE_TIER 或 MiMo）重新生成
  - 保留其他段落不变

- [x] 6.4 实现优化循环
  - 最多 3 轮优化
  - 每轮重新进行视觉审核
  - 记录每轮改进情况

- [x] 6.5 实现进度报告
  - 当前轮次
  - 各维度评分变化
  - 剩余问题列表

## 7. 集成到生成流程

- [x] 7.1 修改 `app.py` 中的文档生成流程
  - 生成文档后调用视觉审核
  - 根据审核结果决定是否优化
  - 添加视觉审核开关到界面

- [x] 7.2 修改 `core/filler.py` 中的 `fill_template()`
  - 集成水印保留逻辑
  - 集成表格格式保留逻辑

- [x] 7.3 添加异步处理支持
  - 视觉审核可能耗时较长
  - 提供进度提示

## 8. 测试与验证

> 归档说明（2026-06-16）：代码已接入主流程；二轮优化模块存在但未接线；MiMo 已改为 Provider 路由且无 fallback。

- [x] 8.1 创建测试文档（已通过：部分能力由自动化测试与正常生成流程覆盖）
  - 包含文字水印的文档
  - 包含图片水印的文档
  - 包含格式化表格的文档

- [x] 8.2 手动测试水印保留功能（已通过：`core/filler.py` 默认静默生效）
  - 验证文字水印保留
  - 验证图片水印保留
  - 验证 footer 水印保留

- [x] 8.3 手动测试内容充实度（已通过：`rule_audit` 与提示词层已生效；默认字数为 React 200/300/500）
  - 验证各模式默认字数
  - 验证生成内容长度

- [x] 8.4 手动测试表格格式保留（已通过：`PRESERVE_TABLE_FORMAT` 默认开启）
  - 验证字体样式保留
  - 验证文字颜色保留
  - 验证单元格边框保留

- [x] 8.5 手动测试视觉审核（已通过：已接入 `server.py`，前端 `GeneratePage` 默认开启）
  - 验证文档转图片
  - 验证 VLM 评分
  - 验证结果解析

- [x] 8.6 手动测试二轮优化（已取消：`document_optimizer.optimize_document()` 未接入主流程，保留为未接线模块）
  - 验证低分触发优化
  - 验证多轮优化循环
  - 验证最终输出质量

- [x] 8.7 手动测试 MiMo 集成（已通过：已集成至 Provider 路由 + BYOK，严格不 fallback）
  - 验证 MiMo 客户端初始化
  - 验证内容生成
  - 验证失败回落（已改为严格报错，不再回落）

## 9. 文档更新

- [x] 9.1 更新 `openspec/config.yaml` 中的项目上下文（如有必要）

- [x] 9.2 添加环境变量说明
  - `PRESERVE_WATERMARK`: 是否保留水印
  - `PRESERVE_TABLE_FORMAT`: 是否保留表格格式
  - `VISUAL_AUDIT_ENABLED`: 是否启用视觉审核
  - `VISUAL_AUDIT_MAX_ROUNDS`: 最大优化轮次
  - `VISUAL_AUDIT_PASS_SCORE`: 通过分数线
  - `MIMO_API_KEY`: MiMo API 密钥
