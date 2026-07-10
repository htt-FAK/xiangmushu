# Draft: firecrawl-web-search

- status: delivered (dual-Momus + Oracle, Round 3 OKAY/OKAY — PASSED)
- slug: firecrawl-web-search
- pending action: $start-work (execute plan via worker)

## User request (paraphrased)
Replace the current LLM-based "联网搜索/联网补充" with Firecrawl MCP Server (free tier,
preferably keyless hosted https://mcp.firecrawl.dev/v2/mcp). Encapsulate it as a reusable
unit the pipeline calls directly. The frontend "联网搜索" button should just toggle whether
this Firecrawl search runs. No need to configure a web-search model anymore.

## Intent routing
CLEAR — outcome is specific (Firecrawl free tier, drop LLM search, toggle stays, remove
search-model config). Genuine forks exist that only the user can decide. Routing to
intent-clear.md.

## Conceptual correction (surfaced to user)
Project is a deterministic generation pipeline, NOT an agent+tool-calling loop. So
"封装成 MCP/skill 让大模型调用" maps to: a Python module (e.g. core/firecrawl_search.py)
wrapping Firecrawl, invoked directly by the pipeline. The frontend toggle already has the
correct semantics (enable_web) — no UI change needed.

## Topology / Components ledger
- C1 Firecrawl client module (NEW) — Python wrapper; access method = FORK
- C2 Evidence-fetch path — replace fetch_web_evidence (web_search_agent.py) with Firecrawl search
- C3 Main-writer inline search — replace extra_body.enable_search injection (generator.py:732-738) with Firecrawl-context injection into prompt; scope = FORK
- C4 Frontend toggle — keep enable_web as-is (adopted default: no UI change)
- C5 Settings UI — remove web_search model dropdown (depends on C3 scope)
- C6 Config/env — remove WEB_SEARCH_MODEL, add FIRECRAWL_* env
- C7 Tests — rewrite test_web_search_agent.py + add Firecrawl client tests (adopted default: tests-after)

## Grounded facts (with paths)
### Backend cost sources (the LLM-token burn to remove)
- core/web_search_agent.py:126 fetch_web_evidence — separate LLM pre-call; profile extra_body enable_search=True (model_router.py:145); MiMo branch uses _MIMO_WEB_SEARCH_TOOLS (web_search_agent.py:18-25)
- core/generator.py:448 call site — gated by `enable_web and (weak_kb or low_similarity) and not fast_mode`
- core/generator.py:732-738 use_plus branch — sets extra_body["enable_search"]=True AND switches model to search module (VISION_WEB_MODEL). This is the MAIN-WRITER inline search path; second cost source
- core/dashscope_chat.py — backup fallback re-injects enable_search on retry (lines 145-347)
- core/web_search.py — legacy Tavily path, unused in main link, returns [] if no TAVILY_API_KEY

### Config (config.py)
- L83 WEB_SEARCH_MODEL default qwen3.7-plus
- L84 WEB_SEARCH_FALLBACK_MODEL_1
- L104 WEB_SEARCH_WRITING_MODE (calm/creative) — prompt flavor, keep
- L102 TEMP_WEB_GEN
- L116 RETRIEVAL_WEB_SIMILARITY_THRESHOLD — gates when web branch triggers, keep
- USER_MODEL_OPTIONS["web_search"] (L253-256) and ROLE catalog

### Model router
- model_router.py:15 WEB_SEARCH role; :132-148 ModelRoleProfile with extra_body enable_search; legacy_module "search"
- generator.py:735 self._model_for_module("search", config.VISION_WEB_MODEL) — main writer switches to search model on use_plus

### Frontend
- SetupPanel.tsx:60 enableWeb toggle, label t("generate.enableWeb")="联网补充"
- GeneratePage.tsx:48 useState(false); :106 smart default enableWeb=!hasRichKB; :260 passed to setup
- payload field: enable_web (bool) in /api/generate
- SettingsPage.tsx:10 MODEL_ROLE_ORDER includes "web_search" → model dropdown to remove
- i18n.ts:178 "generate.enableWeb"; :406 "settings.moduleDesc.web_search"

### Server schema
- server.py:836,946,985,2102,2205 — enable_web: bool threaded through /api/generate and session create

### Existing tests (will need rewriting)
- tests/test_web_search_agent.py — 4 tests asserting LLM-call shape (enable_search, mimo tools, usage, cache)
- tests/test_generation_preferences_and_provider_errors.py:71-132 — mocks fetch_web_evidence

### Stack / infra constraints
- requirements.txt: openai==1.25.0, httpx>=0.27,<0.28 (PINNED, openai 1.25 incompatible with httpx 0.28+), dashscope>=1.20, fastapi, sync stack. NO mcp client, NO async infra currently.
- .env.example: no FIRECRAWL/TAVILY keys; TAVILY only read in legacy core/web_search.py

## Firecrawl facts (librarian-verified)
- Hosted MCP https://mcp.firecrawl.dev/v2/mcp : streamable HTTP, keyless per-IP rate-limited
- Tools: firecrawl_search (query, limit, location, tbs, scrapeOptions), firecrawl_scrape (url, formats, onlyMainContent...), firecrawl_interact
- Free keyless limits: search 5/min, scrape 10/min, 2 concurrent browsers; daily cap exact number UNVERIFIED
- Official Python SDK firecrawl-py v4.31.0 → REST /v1/, REQUIRES api_key, does NOT do keyless
- Keyless from Python ⇒ need an MCP client lib (mcp Python SDK / fastmcp) connecting to hosted MCP endpoint
- Alt keyless-ish: free Firecrawl API key (500 credits/mo) + firecrawl-py sync SDK
- OSS self-host: AGPL-3.0, heavy infra (Node/Redis/browser pool)
- GitHub: firecrawl/firecrawl 146k stars, firecrawl/firecrawl-mcp-server 6.9k stars

## Surviving forks (to ask)
- F1 Firecrawl access method: keyless MCP-client (matches "免key" but adds MCP client dep + async + shared-IP throttle risk) / free API key SDK (simple sync, but needs a key, 500 credits/mo) / self-host OSS (no limits, heavy infra)
- F2 Replacement scope: replace BOTH cost sources (max savings, biggest refactor, web_search role fully removed) / only evidence pre-step fetch_web_evidence (smaller change, main-writer enable_search + search model remain)

## Adopted defaults (will state in brief, user can veto)
- D-failure: silent skip when Firecrawl unavailable/rate-limited (matches current graceful behavior at generator.py:458-459); no fallback to LLM search (would keep cost)
- D-frontend: keep "联网补充" label and enable_web semantics; no UI change (already correct)
- D-settings: remove web_search dropdown IF F2=both; keep IF F2=evidence-only
- D-tests: rewrite test_web_search_agent.py to assert Firecrawl call shape; add core/firecrawl_search.py unit tests with mocked transport; update test_generation_preferences_and_provider_errors.py mocks. Tests-after (no TDD).
- D-config: remove WEB_SEARCH_MODEL / WEB_SEARCH_FALLBACK_MODEL_1 from config.py + .env.example + USER_MODEL_OPTIONS when role fully removed; add FIRECRAWL_MCP_URL (default https://mcp.firecrawl.dev/v2/mcp), FIRECRAWL_SEARCH_LIMIT (default 5), FIRECRAWL_TIMEOUT (default 30), FIRECRAWL_ENABLED (default True). NO FIRECRAWL_API_KEY (Must-NOT #2 explicitly forbids introducing one).
- D-encapsulation: core/firecrawl_search.py module exposing search_web_evidence(query, ...) -> WebFact-like list; replace core/web_search.py (legacy Tavily) usage too

## Resolved forks (user answered 2026-07-07)
- F1 = 免 key + MCP client (keyless hosted MCP). User explicitly wants zero key.
- F2 = 两处都换 (replace BOTH cost sources; web_search role fully removed).

## Confirmed technical facts (librarian, 2nd wave)
- httpx `iter_lines()` exists in 0.27.x; `with client.stream("POST", ...) as r` works. So a hand-rolled minimal MCP streamable-HTTP client on the EXISTING httpx pin (<0.28) is feasible — NO new SDK dependency, NO async. [UNVERIFIED-at-impl: whether hosted Firecrawl MCP requires Mcp-Session-Id handshake or accepts stateless POST; spec allows both, worker resolves empirically in ~5 min, fallback path specified]
- Firecrawl keyless needs NO Authorization header — only standard MCP headers (Accept, Content-Type, Mcp-Session-Id if returned). [docs.firecrawl.dev/mcp-server]
- MCP streamable-HTTP: POST JSON-RPC envelope; response may be single JSON or SSE (text/event-stream with `data:` lines). tools/call body = {"jsonrpc":"2.0","id":N,"method":"tools/call","params":{"name":"firecrawl_search","arguments":{...}}}.

## Chosen approach (for approval)
- NEW core/firecrawl_search.py: minimal sync MCP streamable-HTTP client on existing httpx; exposes search_web_evidence(query, limit, timeout) -> list[WebFact]. Stateless POST first; if server demands session, do init+notifications/initialized handshake, cache Mcp-Session-Id per process. No API key. Config: FIRECRAWL_MCP_URL (default https://mcp.firecrawl.dev/v2/mcp), FIRECRAWL_SEARCH_LIMIT (default 5), FIRECRAWL_TIMEOUT (default 30), FIRECRAWL_ENABLED (default 1).
- Replace fetch_web_evidence body: keep signature/return (WebEvidenceResult with facts/gaps) but instead of an LLM call, call firecrawl_search for a query derived from task.target_chapter + task.description; map results to WebFact(claim=content/title, source=url, confidence="unknown", use_for=[]). Drop profile/model/usage (set model="firecrawl-keyless", usage=None). Keep SessionWebEvidenceCache as-is (still useful).
- Replace main-writer use_plus branch (generator.py:733-738): do NOT set extra_body["enable_search"]; do NOT switch model to search/VISION_WEB_MODEL. Instead, when use_plus would have been true, call firecrawl_search and inject snippets into retrieved_texts/ref block of the prompt. generation_tier becomes "main_writer_web_evidence" (already exists at generator.py:556) consistently. Model stays MAIN_WRITER/LARGE_LLM_MODEL.
- Remove WEB_SEARCH role entirely: model_router.py:132-148, LEGACY_MODULE_TO_ROLE["search"], ROLE_TO_LEGACY_MODULE[WEB_SEARCH], USER_MODEL_OPTIONS["web_search"], config WEB_SEARCH_MODEL + WEB_SEARCH_FALLBACK_MODEL_1. SettingsPage MODEL_ROLE_ORDER drop "web_search". i18n settings.moduleDesc.web_search drop. Provider copy mentioning 联网搜索 (SettingsPage lines 41/444/446/511) updated to note Firecrawl.
- dashscope_chat.py for_enable_search branches (145-157,165-170,250-347): become dead code (enable_search never set) — leave as defensive no-ops or remove; plan says remove for cleanliness with a regression test.
- core/web_search.py (legacy Tavily): delete; nothing imports it after fetch_web_evidence rewrite. TAVILY_API_KEY env removed from docs.
- Failure mode (adopted default, user can veto): silent skip — on Firecrawl error/timeout/rate-limit, web enrichment is skipped, generation continues KB-only, gap note appended (matches current generator.py:458-459). NO fallback to LLM enable_search (would reintroduce cost).
- Frontend (adopted default): keep "联网补充" label + enable_web semantics; no UI change.
- Tests (adopted default, tests-after): rewrite tests/test_web_search_agent.py to assert firecrawl call (mock httpx transport) not LLM call; add tests/test_firecrawl_search.py for client (SSE parse, session fallback, error→[], keyless headers); update tests/test_generation_preferences_and_provider_errors.py mocks; smoke_test_models.py enable_search probe rows become informational-only or removed.

## Approval gate
status: DELIVERED — dual high-accuracy review PASSED (both Momus + Oracle OKAY on round 3). Plan at .omo/plans/firecrawl-web-search.md is handoff-ready. Awaiting user's $start-work to begin execution.

Review history:
- R1: Momus NEEDS-FIX (C1 blocking: T4 referenced nonexistent evidence_pack) + Oracle NEEDS-FIX (R1 JSON-RPC error, R3 throttle)
- R2 (after 5 fixes): Momus OKAY + Oracle NEEDS-FIX (T4 QA wording + R4 prompt checklist incomplete)
- R3 (after 2 more fixes): Momus OKAY + Oracle OKAY — PASSED
