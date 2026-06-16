## 1. 后端线程与事件推送修复

- [x] 1.1 在 `server.py` 的 `_run_generation_session` 中，删除生成线程池运行前、瞬间发出全部章节任务事件的 pre-run 循环代码。
- [x] 1.2 在 `server.py` 的 `_generate_one_task` 子线程任务体的开头，实时发出 `{"type": "task", "index": i, "total": len(tasks), "chapter": task.target_chapter}` 事件，使进度与生成步调一致。
- [x] 1.3 确保在 `_run_generation_session` 生成抛出严重异常（尤其是大异常或数据库彻底无法写入时），后端能通过 try-except 块正确向上层发送最终的 `"error"` 信号，修正 Session 状态为 `"error"`，避免幽灵会话死锁为 `"running"`。

## 2. 静态审计状态步骤隔离与数据库降级

- [x] 2.1 修改 `server.py` 中的 `result["audit"]` 事件参数，新增并传递 `"is_model_audit"` 标志（在 `local_auditor is not None` 时为 `True`，否则为 `False`）。
- [x] 2.2 修改 `core/generation_sessions.py` 中的 `_apply_event` 处理，只有在 `"type": "audit"` 事件的 `"is_model_audit"` 为 `True` 或不传递时，才切换 Session 的 `current_step = "audit"`；对于本地静态审计，仅将 issues 保存到对应的 Block 中而不发生全局 Step 状态改变。
- [x] 2.3 修改 `core/auth.py` 的 `get_user_preferences` 以及模型获取偏好代码。捕获 MySQL 异常连接异常，加载失败时降级为内存 defaults 并传递明确的 `"warnings"`，警告用户发生了数据库连接降级而非无声失效。

## 3. 前端交互状态锁定与静态审计步骤区分

- [x] 3.1 修改 `frontend/src/pages/generate/useGenerationSession.ts` 的 `"audit"` 事件规约处理：只有在 `event.is_model_audit !== false` 时才设置全局步骤为 `"audit"`（`setCurrentStep("audit")`）。
- [x] 3.2 在 `frontend/src/pages/GeneratePage.tsx` 中增加页面已完成或正在执行的 `hasGeneratedOutputs` 或者 `busy` 判断，用于死锁配置项状态。
- [x] 3.3 修改 `frontend/src/pages/generate/SetupPanel.tsx`，将 Quality Mode 下拉/单选框、联网搜索和审核等高级 Toggle 的 `disabled` 属性不仅绑定 to 原有的 `busy` 状态，还要在 `outputs.length > 0` 且会话正常处于非空时处于完全死锁（disabled）状态。

## 4. 全中文国际化清理与英文硬编码/英文Fallback

- [x] 4.1 翻译 `frontend/src/pages/HistoryPage.tsx` 中的全部硬编码英文词汇。将 `"Backend unavailable"` 翻译为 `"后端服务未连接"`，`"Loading history..."` 翻译为 `"正在加载历史记录..."`，`"No records match the current filters."` 翻译为 `"没有符合当前筛选条件的历史记录。"`，`"History records are not available right now."` 翻译为 `"当前无法获取历史记录。"`，将 `tokens` 统一汉化。
- [x] 4.2 翻译 `frontend/src/pages/TemplateAnalysisPage.tsx` 中 Stats 看板的硬编码英文。将 `Input tokens` / `Output tokens` / `Cost CNY` 汉化为对应中文。
- [x] 4.3 翻译 `frontend/src/pages/TemplateAnalysisPage.tsx` 中属性表格里的英文标签（`Vision model` -> `视觉模型`，`Planner model` -> `规划模型`，`Phase` -> `分析阶段`，`Status` -> `分析状态`）。
- [x] 4.4 优化 `frontend/src/pages/TemplateAnalysisPage.tsx` 中的接口错误 Fallback。将 normalizeErrorMessage 中的 `"Failed to load templates."` 等英文错误 Fallback 文本统一翻译为直观的中文。
- [x] 4.5 优化 `frontend/src/pages/KnowledgeBasePage.tsx`，将 `"Slug"` 标签更改为 `"标识符 (Slug)"`，将解析切片提示 `chunks` 翻译为中文。
