## Why

The current generation flow mixes model roles, runtime tiers, web search, RAG recall, and user model choices inside task-level generation code, which makes the system hard to reason about and causes excessive token usage. We need a clearer agent-oriented routing model where a main writing agent produces final content from compact evidence packs, while branch agents only retrieve, search, compress, inspect, or audit.

## What Changes

- Introduce a generation agent routing capability that separates the main content writer from branch agents for knowledge retrieval, web search, visual/layout understanding, template planning, evidence compression, and audit.
- Make DeepSeek v4 Pro the default main writing model while preserving user choice for each model role.
- Change web search from a direct generation tier into a branch evidence agent: it searches and extracts structured web facts, then passes those facts to the main writing agent together with knowledge-base evidence.
- Replace repeated task-level full recall with compact per-session and per-task evidence packs to reduce duplicate prompt tokens.
- Add a centralized model role registry/router that resolves role, model, fallbacks, temperature, provider flags, and routing reason before any model call.
- Split template visual understanding from template planning so selecting a visual model does not implicitly select the task-planning model.
- Keep existing generation APIs usable, but enrich trace/report metadata so users can see which role and model produced search evidence, final content, and audit decisions.
- **BREAKING** for internal configuration semantics: legacy model config keys may remain as compatibility aliases, but new code should route through role-based profiles instead of reading scattered model variables directly.

## Capabilities

### New Capabilities
- `generation-agent-routing`: Defines role-based model routing, evidence-pack construction, main-writer orchestration, branch-agent responsibilities, and token-saving behavior for generation sessions.

### Modified Capabilities
- `chapter-paragraph-fill`: Generated paragraph/table-cell content must come from the main writing agent using compact evidence packs instead of branch agents directly producing final text.
- `generate-control-switches`: Existing controls for web enrichment, streaming, audit, and quality/speed modes must map to the new agent roles and token-budget behavior.

## Impact

- Backend generation flow: `core/generator.py`, `core/batch_generator.py`, `server.py`, session event payloads, generation traces, and quality reports.
- Model configuration: `config.py`, user preference storage/reading, settings-page model options, quota-alert model switching, and compatibility aliases for existing environment variables.
- Evidence flow: vector-store retrieval, full-recall behavior, web-search integration, evidence compression, evidence references, and per-session caching.
- Template analysis: `core/template_vision.py`, `core/template_analyzer.py`, and template analysis endpoints must separate visual model choice from planner model choice.
- Audit flow: `core/content_auditor.py` should consume compact evidence used by the main writer and resolve its model through the role router.
- Frontend settings and trace UI: model choices should be presented by user-facing roles such as main writing, web search, fast fill, template vision, template planning, and audit.
