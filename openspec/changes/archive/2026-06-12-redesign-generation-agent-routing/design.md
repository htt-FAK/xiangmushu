## Context

The current generation path decides model choice inside each task-level generation request. A single task can independently decide whether to use the large model, small RAG model, web-enabled model, table vision model, or fast table model. This made sense while the system was growing feature by feature, but it now has three problems:

1. Model roles are mixed with runtime tiers. Users choose modules such as generation, lightweight, vision, search, and audit, while code emits tiers such as large, small_rag, vision_web, table_cell_vision, and table_cell_fast.
2. Web search is treated as a generation tier. When web enrichment is enabled, the search-capable model can become the direct writer instead of serving the main writer with structured evidence.
3. Token use is high. Full recall and repeated per-task evidence assembly can cause the same knowledge-base material to be sent many times across one document generation session.

The desired mental model is agent-oriented:

```text
                           Generation Session
                                  |
                                  v
                        +--------------------+
                        |  Main Writer Agent |
                        | final document text|
                        +---------+----------+
                                  ^
                                  |
                        +---------+----------+
                        |    Evidence Pack   |
                        | compact, cited,    |
                        | deduped, scoped    |
                        +---------+----------+
                                  ^
              +-------------------+-------------------+
              |                   |                   |
              v                   v                   v
      +---------------+   +---------------+   +---------------+
      | KB Retriever  |   | Web Search    |   | Vision/Layout |
      | branch agent  |   | branch agent  |   | branch agent  |
      +---------------+   +---------------+   +---------------+
```

In this model, branch agents find, inspect, compress, and verify. Only the main writer produces final paragraph/table-cell text.

## Goals / Non-Goals

**Goals:**

- Reduce prompt token use by replacing repeated full recall with compact evidence packs.
- Make DeepSeek v4 Pro the default main writing model while preserving role-based user choice.
- Convert web enrichment into a search-and-extract branch agent that returns structured web facts for the main writer.
- Introduce a centralized model router that resolves model role, primary model, fallback chain, temperature, provider flags, and routing reason.
- Separate template visual understanding from template planning.
- Keep existing generation endpoints and session recovery behavior available while internal routing changes.
- Expose trace metadata that explains which role/model performed search, writing, and audit.

**Non-Goals:**

- No durable distributed job queue or worker system.
- No guarantee that one API key can access every optional model role.
- No full rewrite of Word filling, deterministic slot scanning, or document rendering.
- No change to the basic user workflow of choosing a knowledge base, choosing a template, and starting generation.
- No requirement to remove all legacy config keys immediately; compatibility aliases are acceptable during migration.

## Decisions

### Decision: Add a role-based model registry and router

Introduce a role-based registry with user-facing roles:

```text
main_writer        default deepseek-v4-pro
fast_writer        default qwen3.6-flash
web_search         default qwen3.7-plus with enable_search
vision_layout      default qwen3.7-plus
template_planner   default qwen3.7-plus or configured planner model
audit_text         default qwen3.6-flash
embedding          default text-embedding-v4
```

The router returns a resolved call profile:

```text
role
primary_model
fallback_models
temperature
extra_body flags
provider handling hints
routing_reason
```

Why this over scattered config variables:

- It gives one place to explain and test routing decisions.
- It makes user settings match runtime behavior.
- It allows quota alerts to point to the role that failed instead of leaking internal tier names.

Alternative considered:

- Keep existing config variables and only change their defaults. Rejected because it would not solve the conceptual confusion or traceability problem.

### Decision: Make the main writer the only producer of final content

Paragraphs and table-cell answers SHALL be produced by the main writer flow. Branch agents can produce evidence, visual notes, critique, or structured plans, but not final document body text.

Why:

- It centralizes style, tone, language, and evidence integration.
- It avoids web search output competing with RAG output.
- It keeps DeepSeek v4 Pro useful as the primary writer without forcing every support task to use it.

Alternative considered:

- Continue letting web-enabled generation directly write content. Rejected because it blurs responsibility and makes it harder to combine knowledge-base and web evidence consistently.

### Decision: Build compact evidence packs before writing

Generation should create evidence packs with two levels:

```text
Session Evidence Pack
  - reusable project facts
  - common policy/industry facts
  - user instructions
  - template-level visual/planning notes

Task Evidence Pack
  - task-specific KB facts
  - task-specific web facts
  - relevant table/section context
  - gaps and confidence notes
```

The main writer receives only the task evidence pack plus relevant session evidence, not the entire knowledge base unless the token budget explicitly allows it.

Why:

- It reduces repeated prompt tokens across many FillTasks.
- It makes evidence visible and auditable.
- It allows web search results to be cached and reused.

Alternative considered:

- Keep full recall but lower its max chars. This would reduce cost somewhat, but still duplicates evidence per task and does not fix web/search responsibility.

### Decision: Treat web search as structured evidence extraction

When web enrichment is enabled and evidence needs web support, the web search branch agent should return a structured summary such as:

```json
{
  "facts": [
    {
      "claim": "...",
      "source": "...",
      "confidence": "high",
      "use_for": ["policy_background"]
    }
  ],
  "gaps": ["..."]
}
```

The main writer combines these web facts with knowledge-base facts. If knowledge-base and web evidence conflict, knowledge-base facts remain preferred unless the task explicitly requests current public information.

Why:

- Search models are optimized for finding and extracting, not necessarily final document voice.
- It reduces duplicate final writing attempts.
- It makes source and confidence metadata available to traces and audit.

Alternative considered:

- Use an external search API before LLM extraction. This can be added later, but the immediate architecture should work with the current OpenAI-compatible `enable_search` model path.

### Decision: Split template vision from template planning

Template visual understanding and template planning should be separate roles:

```text
vision_layout:
  input: template page images
  output: compact visual/layout profile

template_planner:
  input: OOXML text + deterministic scan + optional visual profile
  output: FillTask list
```

Why:

- A user selecting a visual model should not unintentionally select the planner model.
- It makes template analysis trace and billing clearer.
- It allows cheaper planner models or fallback strategies without changing visual extraction.

Alternative considered:

- Keep one template analysis model control. Rejected because the current behavior is one of the visible sources of confusion.

### Decision: Keep compatibility while shifting semantics

Legacy config names can remain as fallback aliases:

```text
LARGE_LLM_MODEL       -> main_writer
SMALL_LLM_MODEL       -> fast_writer
VISION_WEB_MODEL      -> web_search
TEMPLATE_VISION_MODEL -> vision_layout
TEMPLATE_ANALYZE_MODEL -> template_planner
AUDIT_LLM_MODEL       -> audit_text
```

New code should ask the router for a role profile. Existing environment variables should continue to work during migration.

Why:

- This avoids breaking local `.env` files and deployment assumptions.
- It lets implementation move module by module.

Alternative considered:

- Rename all environment variables in one change. Rejected because it increases deployment risk without improving runtime behavior by itself.

## Risks / Trade-offs

- [Risk] Evidence compression can drop useful context. -> Mitigation: keep evidence pack traces, include confidence/gaps, and allow quality mode to use a larger evidence budget.
- [Risk] Adding branch agents may add latency. -> Mitigation: cache session-level web facts and reuse evidence packs across tasks; keep branch calls conditional.
- [Risk] DeepSeek v4 Pro may not be available for every user key. -> Mitigation: role router keeps user choice and fallbacks; quota alerts name the failing role and offer available models.
- [Risk] Compatibility aliases can hide old/new semantics. -> Mitigation: trace both legacy source key and resolved role during migration, then deprecate old names in a later change.
- [Risk] Search facts without robust citations can create trust issues. -> Mitigation: web evidence items must carry source text/URL metadata when available and must be visible in generation traces.
- [Risk] Refactoring generation routing touches many files. -> Mitigation: introduce the router and evidence pack types first, then migrate callers incrementally behind existing endpoints.

## Migration Plan

1. Add role registry and model router with compatibility mapping from existing config keys and user preferences.
2. Add EvidencePack data structures and trace serialization while preserving existing generator inputs.
3. Convert knowledge retrieval from repeated full recall into session/task evidence-pack construction with conservative token budgets.
4. Convert web enrichment into a branch evidence extraction path and feed results into the main writer.
5. Switch `ContentGenerator` and batch table generation to request role profiles from the router.
6. Split template analysis controls into `vision_layout` and `template_planner` roles.
7. Update frontend settings/model options and quota modal copy to show role names.
8. Update tests and smoke flows to verify routing decisions, token-budget behavior, web evidence integration, and backwards-compatible defaults.

Rollback strategy:

- Keep old environment variables as aliases.
- Preserve `/api/generate` and `/api/generate/sessions` contracts.
- If evidence-pack routing fails, fall back to the previous per-task generation path behind a temporary feature flag.

## Open Questions

1. Should quality mode allow a larger task evidence pack or should it also trigger a stronger main writer model by default?
2. What is the exact initial token budget for session evidence and task evidence?
3. Should web evidence be persisted only inside generation-session memory or also saved to report artifacts for later inspection?
4. Should `deepseek-v4-pro` be offered only as the main writer default, or also as a high-quality fallback for template planning and audit?
