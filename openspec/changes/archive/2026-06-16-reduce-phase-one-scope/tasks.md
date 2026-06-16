## Apply View

### Recommended execution order

```text
Step 1  边界与文案
  -> Step 2  模板入口收缩
  -> Step 3  生成主循环收缩
  -> Step 4  生成后尾部收缩
  -> Step 5  依赖与状态清理
  -> Step 6  测试与验收收口
```

### Dependency notes

- Step 2 依赖 Step 1 已明确一期主叙事，否则模板页文案和默认路径会反复变化
- Step 3 依赖 Step 2，否则生成页仍会被旧的模板视觉入口牵制
- Step 4 依赖 Step 3，否则难以判断哪些生成后逻辑已不再属于主流程
- Step 5 依赖 Step 2-4 完成，否则容易过早删掉仍在使用的 import 和 session 键
- Step 6 应最后进行，用于锁定新的回归门禁与验收范围

### Definition of done for the change

- `app.py` 的主流程叙事与 UI 已收缩为“一期初稿生成工具”
- 模板配置默认路径不再依赖 `core.template_vision`
- 生成主循环不再依赖审核、批量表格、页图多模态增强才能成功
- 生成后默认路径不再执行视觉审核或优化提示
- 一期验收标准只要求入库、锚点模板、分段生成、Word 导出和人工复核前初稿质量

## 1. 一期边界落档

> 归档说明（2026-06-16）：Streamlit `app.py` 已移除，产品边界已在 React + `server.py` 架构及后续 OpenSpec changes 中对齐。

- [x] 1.1 在 `openspec/changes/reduce-phase-one-scope/` 中补齐 proposal、design、tasks 与 capability 规格（已取消：artifacts 已存在，无需重复落档）
- [x] 1.2 在相关文档中统一一期定位为“知识库 + 锚点模板 + Word 初稿生成”（已取消：已由 React 首页/生成页与主 specs 取代）
- [x] 1.3 标注一期明确不承诺的内容：视觉审核、自动二轮优化、复杂模板自动识别、复杂版式全保真（已取消：已在后续 specs 与实现中分别处理）

## 2. 第一阶段：先收侧栏与页面叙事

- [x] 2.1 收缩 `app.py` 侧栏“生成设置”区，仅保留一期主配置
- [x] 2.2 在主界面保留以下配置
  - 生成强度
  - 流式显示
  - 联网补料
  - 每段默认字数
- [x] 2.3 将以下开关从主界面移出
  - `adv_use_audit_agent`
  - `adv_audit_regenerate`
  - `adv_visual_audit_enabled`
  - `adv_skip_template_vision`
- [x] 2.4 将以下开关转入二期隐藏层或调试入口
  - `adv_web_writing_mode`
  - `adv_fast_gen`
  - `adv_use_batch_table`
  - `adv_use_mimo`
- [x] 2.5 收缩 `tab_kb` 和首页文案，改为强调一期默认支持 `docx` 与文本层 `pdf`
- [x] 2.6 收缩首页、侧栏说明和标签页描述，避免继续把产品表述为自动审稿或自动修复系统

### 2 完成判据

- [x] 2.a 普通用户仅从侧栏和首页即可理解一期核心流程
- [x] 2.b 主界面不再出现审核 Agent、视觉审核、MiMo、模板视觉相关的默认入口
- [x] 2.c 侧栏保留下来的控件均能直接服务于一期主链路

## 3. 第二阶段：收缩模板分析默认入口

- [x] 3.1 识别 `app.py` 中 `_run_template_vision_and_analyze()` 作为当前模板入口总控函数的耦合点
- [x] 3.2 将模板分析默认路径改为锚点扫描优先，而不是模板视觉优先
- [x] 3.3 在 `tab_tpl` 的“分析模板”按钮流程中，先走锚点模板分析主路径
- [x] 3.4 对未识别到锚点的模板给出一期范围提示，而不是继续走模板视觉分析主路径
- [x] 3.5 将 `core.template_vision` 相关逻辑从模板主入口移出，必要时保留为显式实验入口
- [x] 3.6 清理模板页中与“跳过模板视觉”相关的主流程文案和控件

### 3 完成判据

- [x] 3.a `tab_tpl` 的“分析模板”按钮已经走一期默认路径
- [x] 3.b 含锚点模板可以直接得到 FillTask 列表
- [x] 3.c 无锚点模板不会再自动触发模板视觉作为默认前置步骤

## 4. 第三阶段：收缩生成主循环

- [x] 4.1 以“逐任务检索 -> 逐任务生成 -> 预览 -> Word 回填”为目标重新定义 `tab_gen` 主链路
- [x] 4.2 保留 `ContentGenerator` 与 `WordFiller` 的一期主用法，不在此阶段重写 `core/generator.py` 内部算法
- [x] 4.3 先从 `tab_gen` 中移除任务分组、预检索复用和表格批量生成相关主流程块
- [x] 4.4 将以下逻辑从默认生成主循环中移出
  - `group_tasks(...)`
  - `retrieve_for_group(...)` 驱动的共享 evidence 主路径
  - `batch_generate_table_row(...)`
  - `batch_cache` 结果复用分支
- [x] 4.5 从默认生成主循环中移出表格增强逻辑
  - `build_table_cell_context(...)`
  - `load_table_cell_vision_pngs(...)`
  - 表格页图与多模态增强分支
- [x] 4.6 从默认生成主循环中移出内容审核与审核后重试逻辑
  - `rule_audit(...)`
  - `need_model_audit(...)`
  - `ContentAuditor().audit(...)`
  - `should_apply_revision(...)`
  - 基于审核意见再次生成的 `_make_bundle(hint)` 分支
- [x] 4.7 确保 `tab_gen` 在收缩后仍能完成最小流程
  - 读取模板
  - 读取或生成任务列表
  - 逐任务生成内容
  - 聚合 `results`
  - 回填 Word
  - 提供下载

### 4 完成判据

- [x] 4.a `tab_gen` 的默认路径只剩逐任务生成主链路
- [x] 4.b 去掉批量表格、审核和页图增强后，仍能生成并导出 `.docx`
- [x] 4.c 主循环代码的可读性明显优于现状，普通维护者能快速识别生成主干

## 5. 第四阶段：收缩生成后尾部处理

- [x] 5.1 识别 `app.py` 中 `fill_template(...)` 之后的生成后尾部处理区块
- [x] 5.2 将生成后默认执行的视觉审核流程从主流程中移出
- [x] 5.3 将以下主流程后置逻辑移出或改为独立实验入口
  - `audit_document_visual(...)`
  - `should_optimize(...)`
  - 视觉评分展示
  - 优化提示与保护元素提示
- [x] 5.4 将生成完成后的成功口径收缩为
  - 输出 `.docx` 可正常打开
  - 主要锚点已填充
  - 用户可继续人工复核和修改

### 5 完成判据

- [x] 5.a `fill_template(...)` 之后的默认路径只负责成功提示、预览和下载
- [x] 5.b 不开启任何实验入口时，生成完成后不会再触发视觉审核相关逻辑
- [x] 5.c 用户看到的成功语义已经从“自动审稿”收缩为“生成初稿成功”

## 6. 第五阶段：清理 import、状态项与辅助函数

- [x] 6.1 在主流程完成收缩后，再清理 `app.py` 顶部 import，避免提前删依赖造成判断失真
- [x] 6.2 从主入口依赖中移除或延迟加载以下模块
  - `core.content_auditor`
  - `core.batch_generator`
  - `core.task_grouper`
  - `core.table_context`
  - `core.template_vision`
- [x] 6.3 将主入口依赖收敛到一期链路必需模块
  - `core.kb_extract`
  - `core.vector_store`
  - `core.template_analyzer`
  - `core.generator`
  - `core.filler`
- [x] 6.4 清理不再属于一期主界面的 `st.session_state` 键与相关默认值
  - `adv_use_audit_agent`
  - `adv_audit_regenerate`
  - `adv_use_batch_table`
  - `adv_skip_template_vision`
  - `adv_visual_audit_enabled`
  - `adv_use_mimo`
- [x] 6.5 决定 `_run_template_vision_and_analyze()` 的最终归宿
  - 退化为一期专用模板分析函数
  - 或保留旧函数但不再作为默认入口

### 6 完成判据

- [x] 6.a `app.py` 顶部 import 已与新的主流程一致
- [x] 6.b 不再有明显失效的 session 键、无用控件默认值或遗留文案
- [x] 6.c 实验函数即使保留，也不会继续误导主流程阅读者

## 7. 第六阶段：收缩测试与验收口径

- [x] 7.1 调整回归测试和手工验收，只覆盖一期主链路
- [x] 7.2 将一期验收门禁收敛为
  - `docx` / 文本层 `pdf` 入库
  - 锚点模板分析成功
  - 分段生成成功
  - Word 导出成功
  - 主要锚点替换成功
- [x] 7.3 将视觉审核、自动优化、MiMo 路由、模板视觉、多模态表格增强从一期验收门禁中移除
- [x] 7.4 输出模块分层清单
  - 一期保留
  - 二期隐藏
  - 移出一期路线

### 7 完成判据

- [x] 7.a 团队可以用新的一期门禁判断一次改动是否达标
- [x] 7.b 旧的视觉审核/自动优化要求不再阻塞一期交付
- [x] 7.c 模块分层清单已可用于代码评审和回归测试范围判断

## 8. 文档与首页说明更新

> 归档说明（2026-06-16）：本节原针对 Streamlit `app.py`；当前入口为 React 前端 + `server.py`，本节任务已被新架构 supersede。

- [x] 8.1 更新首页文案，突出“一期是申报类 Word 初稿生成工具”（已取消：已由 `frontend/src/pages/HomePage.tsx` 与 i18n 实现）
- [x] 8.2 更新项目说明文档，加入锚点模板作为一期推荐模板规范（已取消：产品形态已迁移，不再以 Streamlit 文档为准）
- [x] 8.3 在开发文档中补充 `app.py` 收缩清单，标出需要移除、隐藏或改为实验入口的区块（已取消：`app.py` 已删除）

### 8 完成判据

- [x] 8.a 首页、项目说明和 OpenSpec 变更口径一致（已取消：口径已在 React 主 specs 中对齐）
- [x] 8.b 新成员只读文档即可理解一期范围与非目标（已取消：见 `openspec/specs/` 主 specs）
- [x] 8.c 后续实施者可以直接按文档定位 `app.py` 的收缩对象（已取消：目标文件已不存在）
