## 1. Model Roles and Router

- [x] 1.1 Add a role-based model profile module for `main_writer`, `fast_writer`, `web_search`, `vision_layout`, `template_planner`, `audit_text`, and `embedding` in `config.py` or a new `core/model_router.py`.
- [x] 1.2 Map legacy config keys (`LARGE_LLM_MODEL`, `SMALL_LLM_MODEL`, `VISION_WEB_MODEL`, `TEMPLATE_VISION_MODEL`, `TEMPLATE_ANALYZE_MODEL`, `AUDIT_LLM_MODEL`) to the new roles as compatibility aliases.
- [x] 1.3 Update user model preference reading so role choices can be resolved by user id while preserving existing saved `model_choices`.
- [x] 1.4 Implement a router result object containing role, primary model, fallback models, temperature, extra provider flags, and routing reason.
- [x] 1.5 Add unit tests or smoke checks for default role resolution, user override resolution, fallback de-duplication, and DeepSeek v4 Pro as default `main_writer`.

## 2. Evidence Pack Foundation

- [x] 2.1 Add EvidencePack data structures for session-level evidence, task-level evidence, evidence refs, web facts, confidence notes, gaps, and token/character budget metadata.
- [x] 2.2 Add an evidence-pack builder that can combine vector-store results, table context, template visual notes, user instructions, and cached web facts.
- [x] 2.3 Replace default repeated full-recall prompt assembly with compact evidence-pack assembly while keeping a temporary fallback or feature flag for legacy behavior.
- [x] 2.4 Add trace serialization for evidence-pack summaries without exposing excessive raw source text.
- [x] 2.5 Add tests for evidence-pack de-duplication, budget limiting, and conflict marking between knowledge-base and web evidence.

## 3. Web Search Branch Agent

- [x] 3.1 Create a web search branch path that calls the `web_search` role with `enable_search` and returns structured facts instead of final prose.
- [x] 3.2 Cache reusable web facts at generation-session scope so multiple FillTasks can reuse the same search evidence.
- [x] 3.3 Merge web facts into task evidence packs and prefer knowledge-base evidence on conflicts unless a task explicitly requires current public information.
- [x] 3.4 Update generation route metadata to report whether web evidence was requested, used, cached, or skipped.
- [x] 3.5 Add tests or smoke checks showing that enabling web enrichment still routes final writing through `main_writer`.

## 4. Main Writer Generation Migration

- [x] 4.1 Update `core/generator.py` so paragraph and table-cell final content is produced through the `main_writer` or `fast_writer` role using evidence packs.
- [x] 4.2 Update `core/batch_generator.py` so batch table generation follows the same main-writer/faster-writer role semantics and never inserts direct branch-agent output.
- [x] 4.3 Preserve existing filler behavior for placeholders, instruction lines, bracket fill slots, abstract-like chapters, scanner reconciliation, and post-fill sweeps.
- [x] 4.4 Update quota error handling so quota alerts identify the failed role and available models for that role.
- [x] 4.5 Add regression tests for paragraph generation routing, table-cell routing, and existing fill-slot behavior after the routing change.

## 5. Template Vision and Planner Split

- [x] 5.1 Split template analysis model selection into independent `vision_layout` and `template_planner` roles in backend endpoints.
- [x] 5.2 Update `core/template_vision.py` to resolve visual calls through the `vision_layout` role.
- [x] 5.3 Update `core/template_analyzer.py` to resolve planning calls through the `template_planner` role and consume visual profiles as input evidence.
- [x] 5.4 Update template analysis billing and response metadata to report visual and planner models separately.
- [x] 5.5 Add tests or manual smoke checks proving that selecting a visual model does not change the planner model.

## 6. Audit and Reporting

- [x] 6.1 Update `core/content_auditor.py` to resolve the `audit_text` role through the router instead of reading audit config directly.
- [x] 6.2 Make model audit consume the same compact evidence pack used by the writer, plus generated output and task requirements.
- [x] 6.3 Update `core/reporting.py` quality traces to include writer role/model, branch-agent roles/models, evidence-pack summary, and web evidence usage.
- [x] 6.4 Ensure billing records and report summaries continue to aggregate input/output tokens under the resolved model names.

## 7. Frontend Settings and Trace UX

- [x] 7.1 Update `/api/user/model-options` payload or adapter logic to expose user-facing role names for main writing, web search, fast fill, template vision, template planning, and audit.
- [x] 7.2 Update `frontend/src/pages/SettingsPage.tsx` to render role-based model choices and preserve compatibility with existing saved preferences.
- [x] 7.3 Update `frontend/src/pages/TemplateAnalysisPage.tsx` to show separate controls for template vision and template planning when needed.
- [x] 7.4 Update `frontend/src/pages/GeneratePage.tsx` trace, quota modal, and generation summaries to use role names instead of internal generation tier names.
- [x] 7.5 Update i18n strings for the new role names and explanations in `frontend/src/i18n.ts`.

## 8. Verification

- [x] 8.1 Run backend tests or targeted smoke tests covering model routing, evidence packs, web branch behavior, template planner split, and audit routing.
- [x] 8.2 Run frontend type/build checks after settings and trace UI changes.
- [x] 8.3 Run an end-to-end generation smoke test with web enrichment disabled and confirm DeepSeek v4 Pro is the default main writer.
- [x] 8.4 Run an end-to-end generation smoke test with web enrichment enabled and confirm web search produces evidence while final content comes from the main writer.
- [x] 8.5 Validate OpenSpec status for `redesign-generation-agent-routing` and ensure all implementation tasks are tracked.
