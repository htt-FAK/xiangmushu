# Implementation Tasks: Multi-Custom-Models

> **Change**: multi-custom-models
> **Specs**: `multi-model-management`, `model-capability-testing`, `multi-model-generation`
> **Status**: Pending implementation

---

## Phase 1: Database Schema & Migration

- [x] **Task 1.1**: Create `user_custom_models` table schema
  - **Description**: Define the new SQLite/MySQL table with all required columns per design.md: `id`, `user_id`, `name`, `base_url`, `model_id` (comma-separated), `encrypted_api_key`, `capabilities` (JSON), `assigned_roles` (JSON), `default_model_id`, `status` (DEFAULT 'untested'), `last_tested_at`, `last_error`, `created_at`, `updated_at`. Add `FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE`. No UNIQUE constraint on `user_id` — multiple models per user allowed.
  - **Dependencies**: None
  - **Files**: `migrations/mysql/006_user_custom_models.sql`
  - **Acceptance**: Table created with correct schema; tested on both SQLite (local dev) and MySQL (production)

- [x] **Task 1.2**: Write data migration script from `user_custom_audit_models`
  - **Description**: Create migration that copies existing `user_custom_audit_models` rows into `user_custom_models`. Map fields: `user_id → user_id`, `name → name`, `base_url → base_url`, `model_id → model_id`, `encrypted_api_key → encrypted_api_key`, `model_id → default_model_id`, `status → status` (preserving 'validated'). Set empty JSON arrays `[]` for `capabilities` and `assigned_roles`. Old table remains but is marked deprecated.
  - **Dependencies**: Task 1.1
  - **Files**: `migrations/mysql/006_user_custom_models.sql` (migration section)
  - **Acceptance**: After migration, every row in old table has a corresponding row in new table; old table data untouched; `status='validated'` preserved

- [x] **Task 1.3**: Add `user_custom_models` CRUD methods to `core/db.py`
  - **Description**: Implement database helper functions: `create_custom_model(user_id, name, base_url, model_id, encrypted_api_key, default_model_id)`, `get_custom_models_by_user(user_id)`, `get_custom_model_by_id(id, user_id)`, `update_custom_model(id, user_id, **kwargs)`, `delete_custom_model(id, user_id)`, `get_custom_models_by_capability(user_id, capability)`, `get_custom_models_by_role(user_id, role)`. All methods use parameterized queries. Results ordered by `created_at` descending.
  - **Dependencies**: Task 1.1
  - **Files**: `core/db.py`
  - **Acceptance**: All CRUD methods functional; `get_custom_models_by_user()` returns empty list `[]` when no models exist (not None/error)

- [x] **Task 1.4**: Add Fernet encryption helpers for API key storage
  - **Description**: Verify that `core/billing.py`'s `encrypt_api_key()` and `decrypt_api_key()` functions are reusable for the new table. If not, create wrapper functions in `core/db.py` or a new `core/custom_models.py` module. API key preview (masked) generation: first 4 chars + `...` + last 2 chars (e.g., `sk-a1...ef`).
  - **Dependencies**: None
  - **Files**: `core/billing.py`, `core/custom_models.py` (new)
  - **Acceptance**: `encrypt_api_key('sk-abc123def')` returns encrypted string; `decrypt_api_key(encrypted)` returns original; `mask_api_key('sk-abc123def')` returns `'sk-a...ef'`

---

## Phase 2: Backend API Implementation

### 2.1: Core CRUD Endpoints

- [x] **Task 2.1**: Implement `GET /api/user/custom-models` list endpoint
  - **Description**: Authenticated endpoint (requires `get_current_user` dependency). Returns `{"models": [...]}` with all user's custom models. Each model includes: `id`, `name`, `base_url`, `model_id`, `default_model_id`, `capabilities`, `assigned_roles`, `status`, `last_tested_at`, `last_error`, `api_key_preview` (masked, never plaintext), `created_at`, `updated_at`. Empty list returns `{"models": []}` (200, not 404).
  - **Dependencies**: Task 1.3
  - **Files**: `server.py` (new route), `core/custom_models.py`
  - **Acceptance**: Endpoint returns correct JSON schema; no API key leakage; authenticated user isolation verified

- [x] **Task 2.2**: Implement `POST /api/user/custom-models` create endpoint
  - **Description**: Accept `name`, `base_url`, `model_id`, `api_key`, optional `default_model_id`. Validation: non-empty name, valid URL format (SSRF protection via `validate_base_url` from `core/custom_audit.py`), non-empty model_id, non-empty api_key (min 8 chars). Perform live probe via `probe_custom_model()` before saving — on failure return 422 with `{code, message}`. On success save with `status='validated'`. Rate limit: max 10 creations per user per hour. If `model_id` is comma-separated and no `default_model_id`, use first ID as default.
  - **Dependencies**: Task 1.3, Task 2.5 (probe function)
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: Valid creation returns 201 with full model object; invalid URL returns 422 `ssrf_rejected`; probe failure returns 422 with structured error; rate limiting enforced

- [x] **Task 2.3**: Implement `PUT /api/user/custom-models/{id}` update endpoint
  - **Description**: Partial update — only provided fields are updated. If `base_url`, `model_id`, or `api_key` changes, trigger new probe. If only `name` or `assigned_roles` changes, skip probe. Validate `assigned_roles` against allowed set: `text-gen`, `vision`, `embedding`, `audit`, `small-llm`. Auto-refresh `updated_at` timestamp. Return 404 if model doesn't exist or doesn't belong to current user.
  - **Dependencies**: Task 1.3, Task 2.5
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: Partial updates work correctly; probe triggered on connection field changes; 404 for unauthorized access; `updated_at` refreshed

- [x] **Task 2.4**: Implement `DELETE /api/user/custom-models/{id}` endpoint
  - **Description**: Remove model and encrypted API key from database. Return `204 No Content` on success. Return 404 if model doesn't exist or doesn't belong to user. Log audit event (`API_KEY_DELETED` with model ID). Frontend handles confirmation dialog — no secondary confirmation endpoint needed.
  - **Dependencies**: Task 1.3
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: Successful deletion returns 204; model and key removed from DB; audit log entry created; 404 for unauthorized attempts

### 2.2: Capability Testing

- [x] **Task 2.5**: Implement `probe_custom_model()` function for live model validation
  - **Description**: Create probe function that sends minimal requests to verify model connectivity before save. Used by create/update endpoints. Sends simple `POST /chat/completions` with prompt `"Say hello in one sentence."` using 30s timeout. Returns `{success: bool, error?: string}`. Decrypt API key in-memory, never log key material.
  - **Dependencies**: Task 1.4
  - **Files**: `core/custom_models.py` (new)
  - **Acceptance**: Probe returns `{success: true}` for valid model; `{success: false, error: "..."}` for invalid credentials/unreachable endpoint; 30s timeout enforced

- [x] **Task 2.6**: Implement `POST /api/user/custom-models/{id}/test` capability testing endpoint
  - **Description**: Accept optional `test_types` array (`["text", "vision", "embedding"]`); default to all three. Run tests sequentially (not parallel) to respect rate limits. Persist `capabilities`, `last_tested_at`, `last_error` to DB. Return: `id`, `capabilities`, `suggested_roles`, `status` ('tested' or 'untested'), `last_tested_at`, `last_error`, `test_results` (per-test breakdown with `passed`, `latency_ms`, `detail`). If API key invalid (auth error), reject entire test with 422.
  - **Dependencies**: Task 2.7, Task 2.8, Task 2.9
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: All three tests run; partial success saved correctly; auth failure returns 422; rate limit: max 5 tests per model per hour

- [x] **Task 2.7**: Implement text capability probe
  - **Description**: Send `POST /chat/completions` with prompt `"Say hello in one sentence."` using model's `default_model_id`. 30s timeout. Validate response contains non-empty `choices[0].message.content`. On success, add `"text"` to capabilities. On failure, record reason in `last_error`.
  - **Dependencies**: Task 1.4
  - **Files**: `core/custom_models.py`
  - **Acceptance**: Text test passes for valid text models; fails gracefully for non-text models; timeout enforced; error reason specific (e.g., "connection timeout", "empty response", "401 unauthorized")

- [x] **Task 2.8**: Implement vision capability probe
  - **Description**: Send `POST /chat/completions` with embedded base64 test image (10x10 solid cyan PNG, ~100 bytes) and prompt `"Describe the color of this image in one word."` using OpenAI-compatible `content` array with `image_url` type. 60s timeout. Validate non-empty `choices[0].message.content`. On success, add `"vision"`. On failure (400/422 for unsupported image), record "model does not support image input".
  - **Dependencies**: Task 1.4
  - **Files**: `core/custom_models.py`
  - **Acceptance**: Vision test passes for multimodal models (Qwen-VL, GPT-4V); fails cleanly for text-only models; test image hardcoded in backend (no external fetch); 60s timeout

- [x] **Task 2.9**: Implement embedding capability probe
  - **Description**: Send `POST /embeddings` with input `"Test embedding for capability detection."` on same `base_url`. Try model's `default_model_id` first, then attempt `text-embedding-` prefixed variants if primary fails. 30s timeout. Validate response contains non-empty `data[0].embedding` array with numeric values. On success, add `"embedding"`.
  - **Dependencies**: Task 1.4
  - **Files**: `core/custom_models.py`
  - **Acceptance**: Embedding test passes for embedding-compatible models (text-embedding-v3); fails for chat-only endpoints; fallback naming logic works

- [x] **Task 2.10**: Implement role suggestion logic
  - **Description**: Based on detected capabilities, compute `suggested_roles`: `text` → `text-gen`; `vision` → `vision`; `embedding` → `embedding`. Heuristic additions: `text` + model name contains "qwen/gpt/claude/deepseek" → also suggest `"audit"`; `text` + model_id contains "small/mini/turbo" → also suggest `"small-llm"`. Return in confidence order: `["text-gen", "vision", "embedding", "audit", "small-llm"]`.
  - **Dependencies**: None
  - **Files**: `core/custom_models.py`
  - **Acceptance**: Suggestions match heuristic rules; order preserved; advisory only (not enforced)

### 2.3: Role Assignment

- [x] **Task 2.11**: Implement `POST /api/user/custom-models/{id}/assign` endpoint
  - **Description**: Accept `assigned_roles` (array) and optional `default_model_id`. Validate roles against allowed set: `text-gen`, `vision`, `embedding`, `audit`, `small-llm`. If role assigned without corresponding capability tested, include warning in response: `"vision role assigned but model has not been tested for vision capability"`. Return updated model with new assignments.
  - **Dependencies**: Task 1.3
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: Valid roles assigned; warnings returned for untested capability assignments; multiple models can share same role; default_model_id updated correctly

- [x] **Task 2.12**: Add manual capability override support to PUT endpoint
  - **Description**: Extend `PUT /api/user/custom-models/{id}` to accept optional `capabilities` field. When manually set, change `status` to `'override'` (distinct from `'tested'`). Do not re-test unless user explicitly triggers test endpoint. Frontend distinguishes auto-detected (label "Auto") from manual (label "Manual").
  - **Dependencies**: Task 2.3
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: Manual override sets `status='override'`; capabilities persisted; no auto re-test triggered

---

## Phase 3: Frontend Components

### 3.1: Core Component Tree

- [x] **Task 3.1**: Create `CustomModelsManager` parent component
  - **Description**: Container component integrated into `SettingsPage`. Manages state: model list, loading state, error state, active dialog (add/edit/test). Renders `ModelList` + `AddModelDialog` + `TestResultPanel`. Fetches model list on mount via `fetchCustomModels()`. Handles CRUD operations and coordinates testing/assignment flows. Replaces deprecated `CustomAuditModelCard`.
  - **Dependencies**: Task 3.2, Task 3.3, Task 3.4
  - **Files**: `frontend/src/components/CustomModelsManager.tsx` (new)
  - **Acceptance**: Component renders in SettingsPage; fetches and displays model list; add/edit/delete/test flows functional; empty state shows "Add your first model" CTA

- [x] **Task 3.2**: Create `ModelList` component
  - **Description**: Renders array of models as cards. Sort by status (tested first) then by name alphabetically. Show empty state with illustrative message when no models configured. Show skeleton placeholders during initial fetch.
  - **Dependencies**: Task 3.3
  - **Files**: `frontend/src/components/ModelList.tsx` (new)
  - **Acceptance**: Models rendered as cards; correct sort order; empty state displayed; loading skeletons shown

- [x] **Task 3.3**: Create `ModelCard` component
  - **Description**: Per-model display card showing: model name, base URL (truncated), model ID(s), capability badges (green=supported, gray=untested/unsupported), role badges, status indicator, and action buttons (Test, Edit, Delete). Capability badges show "Auto" or "Manual" label based on status. Delete button triggers confirmation dialog.
  - **Dependencies**: None
  - **Files**: `frontend/src/components/ModelCard.tsx` (new)
  - **Acceptance**: All model info displayed correctly; badges color-coded; action buttons functional; delete confirmation shown; status='override' shows "Manual" label

- [x] **Task 3.4**: Create `AddModelDialog` component
  - **Description**: Modal form for creating/editing models. Fields: `name` (required), `base_url` (required, URL format validated client-side), `model_id` (required, with hint for comma-separated values), `api_key` (required, password input, min 8 chars), `default_model_id` (dropdown populated from parsed model_ids). Show loading spinner on save button during POST. Inline error banners with localized messages (i18n).
  - **Dependencies**: None
  - **Files**: `frontend/src/components/AddModelDialog.tsx` (new)
  - **Acceptance**: Form validation works (required fields, URL format, API key length); dropdown populated from comma-separated model_ids; loading state during save; errors displayed inline

- [x] **Task 3.5**: Create `TestResultPanel` component
  - **Description**: Display test results after capability testing. Show per-capability results: green checkmark (passed), red X (failed), gray dash (skipped). Display latency, error detail if failed. Show `suggested_roles`. Include "Accept Suggestions" button that calls assign endpoint. Allow manual capability override via checkboxes with "Manual" label. Include "Retry" button for failed tests and "Test All" button always available.
  - **Dependencies**: None
  - **Files**: `frontend/src/components/TestResultPanel.tsx` (new)
  - **Acceptance**: Per-capability icons displayed correctly; latency shown; error details for failures; accept button assigns roles; manual override checkbox changes status label; retry/test-all buttons functional

- [x] **Task 3.6**: Create `TestModelButton` component
  - **Description**: Button that triggers capability test for a model. Shows "Test" label when `last_tested_at` is older than 5 minutes or never tested. Shows "Re-test" label when tested within 5 minutes. Show loading spinner during test. Display brief result summary inline (e.g., "✓ text, ✗ vision, ✓ embedding") after test completes.
  - **Dependencies**: None
  - **Files**: `frontend/src/components/TestModelButton.tsx` (new)
  - **Acceptance**: Button label changes based on test recency; loading spinner during test; result summary displayed; 5-minute TTL for "Re-test" label

### 3.2: API Client & State Management

- [x] **Task 3.7**: Add API client functions to `frontend/src/api.ts`
  - **Description**: Implement typed API client functions: `fetchCustomModels(): Promise<CustomModel[]>`, `createCustomModel(data: CreateCustomModelRequest): Promise<CustomModel>`, `updateCustomModel(id: number, data: UpdateCustomModelRequest): Promise<CustomModel>`, `deleteCustomModel(id: number): Promise<void>`, `testModelCapabilities(id: number, testTypes?: string[]): Promise<TestResult>`, `assignModelRoles(id: number, roles: string[], defaultModelId?: string): Promise<CustomModel>`. Use existing `apiBase` for URL resolution. Include proper error handling with typed error responses.
  - **Dependencies**: None
  - **Files**: `frontend/src/api.ts`
  - **Acceptance**: All functions typed correctly; error handling matches backend response schema; tested against mock server

- [x] **Task 3.8**: Add TypeScript types for custom models
  - **Description**: Define interfaces in `frontend/src/types.ts`: `CustomModel`, `CreateCustomModelRequest`, `UpdateCustomModelRequest`, `TestResult`, `CapabilityTestResult`, `CustomModelError`. Align with backend API specification schemas from spec files.
  - **Dependencies**: None
  - **Files**: `frontend/src/types.ts`
  - **Acceptance**: All API request/response types defined; used by API client functions and components; no `any` types

- [x] **Task 3.9**: Add i18n strings for custom models UI
  - **Description**: Add all new UI strings to both `zh` and `en` dictionaries in `frontend/src/i18n.ts` under `settings.customModels.*` namespace. Include: title, add button, form labels, validation messages, capability labels, role labels, status labels, error messages, empty state text, confirmation dialog text, test result labels.
  - **Dependencies**: None
  - **Files**: `frontend/src/i18n.ts`
  - **Acceptance**: All strings present in both languages; used by components via `t()` function; no hardcoded strings in components

### 3.3: Settings Page Integration

- [x] **Task 3.10**: Integrate `CustomModelsManager` into `SettingsPage`
  - **Description**: Replace deprecated `CustomAuditModelCard` with new `CustomModelsManager` component in `SettingsPage.tsx`. Keep old component file but mark as deprecated with comment. Ensure correct layout and section ordering in settings page.
  - **Dependencies**: Task 3.1
  - **Files**: `frontend/src/pages/SettingsPage.tsx`, `frontend/src/pages/CustomAuditModelCard.tsx` (deprecate)
  - **Acceptance**: CustomModelsManager renders in SettingsPage; old CustomAuditModelCard removed from render tree but file retained; page layout intact; no console errors

---

## Phase 4: Generation Page Integration

- [x] **Task 4.1**: Extend `model_options_map_for_user()` to merge custom models
  - **Description**: In `core/provider_registry.py`, extend `model_options_map_for_user()` to query `user_custom_models` and merge into each role's options list. Filter by assigned roles OR auto-matched capabilities: `large_llm` requires `text`; `small_llm` requires `text`; `vision_layout` requires `text` AND `vision`; `audit_text` requires `text`; `embedding` requires `embedding`. Custom models appended AFTER built-in options (not interleaved). Each custom option includes: `source: "custom"`, `custom_model_id: number`, `provider_code: "custom"`, `provider_name: "自定义 / Custom"`, `model`: default_model_id, `label`: "{name} ({model_id})".
  - **Dependencies**: Task 1.3, Task 2.6
  - **Files**: `core/provider_registry.py`
  - **Acceptance**: Custom models appear in correct role dropdowns; built-in options still first; custom options have distinguishing fields; models without capabilities/roles excluded

- [x] **Task 4.2**: Implement backend model resolution for custom models in generation engine
  - **Description**: Extend generation engine's model resolution to check if selected `model_choice` matches any custom model's `default_model_id`. If matched, construct OpenAI-compatible client using custom model's `base_url`, `model_id`, and decrypted `api_key`. If custom model fails (invalid key, unreachable), fall back to platform default and emit warning via SSE. Include `custom_model_id` in route metadata. Works for all five roles.
  - **Dependencies**: Task 1.3, Task 1.4
  - **Files**: `core/generator.py`, `core/custom_models.py`
  - **Acceptance**: Custom model used when selected; fallback to default on failure; SSE route metadata includes `custom_model_id`; all five roles supported; embedding uses `POST /embeddings` endpoint correctly

- [x] **Task 4.3**: Update `ContentAuditor` for custom audit model fallback
  - **Description**: Modify `core/content_auditor.py` to first check `user_custom_models` for models assigned to `audit_text` role, then fall back to old `user_custom_audit_models` table. If both exist, new table takes precedence. Old `get_by_user_id()` in `core/custom_audit.py` remains functional for backward compatibility. Migration copies audit models with `assigned_roles: ["audit_text"]` if capabilities include `text`.
  - **Dependencies**: Task 1.2, Task 1.3
  - **Files**: `core/content_auditor.py`, `core/custom_audit.py`
  - **Acceptance**: Audit uses custom model when assigned; falls back to old table when no new assignment; old endpoint still works; migration preserves audit data

- [x] **Task 4.4**: Update frontend generation page dropdowns
  - **Description**: Modify `GeneratePage.tsx` and model dropdown components to render custom model options with visual differentiation: small "Custom" badge or `⚙` icon, `bg-night-900/50 border-signal-cyan/20` styling per cyberpunk design system. When user selects custom model, save `model_choices` via `PUT /api/user/preferences` with custom model's `default_model_id`. Show `selected_unavailable` warning if previously selected custom model was deleted. No regression when no custom models configured.
  - **Dependencies**: Task 4.1
  - **Files**: `frontend/src/pages/GeneratePage.tsx`, frontend model dropdown component
  - **Acceptance**: Custom models render with visual distinction; selection saved correctly; unavailable model shows warning; dropdown functional with zero custom models

- [x] **Task 4.5**: Integrate custom models with quota switch flow
  - **Description**: When built-in provider returns quota error during generation, extend `switchQuotaModel` flow to show available custom models as alternatives (if matching capabilities). Custom models are not subject to platform quota (user's own key). Display "No quota limit" label for custom models in quota modal. If custom model fails during quota-switch, emit standard error event (no auto-retry).
  - **Dependencies**: Task 4.2
  - **Files**: `frontend/src/pages/GeneratePage.tsx`, `core/generator.py`
  - **Acceptance**: Custom models shown as quota alternatives; "No quota limit" label displayed; custom model failure handled gracefully; no automatic retry chain

- [x] **Task 4.6**: Add frontend caching for model list
  - **Description**: Cache model list in `localStorage` with 5-minute TTL, keyed by user + model ID. Invalidate cache when model configuration (base_url, model_id, api_key) changes. Generation page reads from cache first, fetches fresh only if expired. Test result cache: "Re-test" label within 5 minutes, "Test" when older.
  - **Dependencies**: Task 3.1
  - **Files**: `frontend/src/hooks.ts` or new `frontend/src/useCustomModels.ts`
  - **Acceptance**: Cache hit within 5 minutes; cache miss after expiry; invalidation on config change; generation page uses cached data

---

## Phase 5: Security & Validation

- [x] **Task 5.1**: Implement SSRF protection for `base_url` validation
  - **Description**: Reuse `validate_base_url()` from `core/custom_audit.py` for all custom model URL validation. Block private IPs (10.x, 172.16-31.x, 192.168.x), loopback (127.x, localhost), link-local (169.254.x). DNS resolution check to prevent DNS rebinding. Applied in both create and update endpoints.
  - **Dependencies**: None
  - **Files**: `core/custom_models.py`
  - **Acceptance**: URLs resolving to private/loopback/link-local IPs rejected with 422 `ssrf_rejected`; valid public URLs accepted

- [x] **Task 5.2**: Add API key encryption and masked preview
  - **Description**: All API keys encrypted via Fernet (`encrypt_api_key` from `core/billing.py`) before DB storage. Masked preview generated for list endpoint: first 4 chars + `...` + last 2 chars. API key never returned in plaintext, never logged. Decrypted only in-memory for test/generation requests.
  - **Dependencies**: Task 1.4
  - **Files**: `core/custom_models.py`
  - **Acceptance**: Plaintext key never in API response; never in logs; decryption works for test/generation; masked preview correct format

- [x] **Task 5.3**: Add rate limiting for model operations
  - **Description**: Rate limit: max 10 model creations per user per hour; max 5 capability tests per model per hour. Return 429 Too Many Requests with `Retry-After` header when exceeded. Use in-memory rate counter (per-process, acceptable for single-server deployment).
  - **Dependencies**: None
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: 11th creation in an hour returns 429; 6th test per model in an hour returns 429; counter resets after window

- [x] **Task 5.4**: Add max model limit enforcement
  - **Description**: Each user can configure a maximum of 20 custom models. Check count before creation; return 422 with `{code: "limit_exceeded", message: "Maximum 20 custom models allowed"}` when limit reached.
  - **Dependencies**: Task 1.3
  - **Files**: `server.py`, `core/custom_models.py`
  - **Acceptance**: 21st model creation rejected with descriptive error; count check before probe (save API calls)

- [x] **Task 5.5**: Secure test request logging
  - **Description**: All test requests/responses logged at `DEBUG` level only (never `INFO` or above). Log fields: `model_id`, `test_type`, `status_code`, `latency_ms`. No API key material in logs. Sensitive fields explicitly scrubbed.
  - **Dependencies**: Task 2.6
  - **Files**: `core/custom_models.py`
  - **Acceptance**: DEBUG logs contain test metadata; no INFO/WARNING logs contain keys; audit trail available for debugging

---

## Phase 6: Testing

### 6.1: Unit Tests

- [x] **Task 6.1**: Unit tests for capability testing logic
  - **Description**: Test text probe with valid/invalid API key, mock responses. Test vision probe with base64 image encoding. Test embedding probe with `POST /embeddings` format. Test timeout handling (30s text, 60s vision, 30s embedding). Test partial success scenarios. Test auth error rejection (entire test fails).
  - **Dependencies**: Task 2.7, Task 2.8, Task 2.9
  - **Files**: `tests/test_custom_models.py` (new)
  - **Acceptance**: All probe functions tested with mocked HTTP; timeout enforcement; partial success saved; auth failure rejects all

- [x] **Task 6.2**: Unit tests for CRUD database operations
  - **Description**: Test create, read, update, delete operations on `user_custom_models`. Test `get_custom_models_by_user()` returns empty list for new user. Test partial updates only modify specified fields. Test `updated_at` auto-refresh. Test multi-model per user (no UNIQUE constraint). Test cascade delete on user deletion.
  - **Dependencies**: Task 1.3
  - **Files**: `tests/test_db_custom_models.py` (new)
  - **Acceptance**: All CRUD operations verified; edge cases (empty list, partial update, cascade) covered

- [x] **Task 6.3**: Unit tests for role suggestion logic
  - **Description**: Test heuristic rules: text→text-gen, vision→vision, embedding→embedding. Test audit suggestion for "qwen/gpt/claude/deepseek" names. Test small-llm suggestion for "small/mini/turbo" IDs. Test confidence ordering. Test no suggestions for zero capabilities.
  - **Dependencies**: Task 2.10
  - **Files**: `tests/test_custom_models.py`
  - **Acceptance**: All heuristic rules verified; edge cases (no capabilities, multiple matches) covered

- [x] **Task 6.4**: Unit tests for API endpoint validation
  - **Description**: Test all endpoints with valid/invalid inputs. Test SSRF URL rejection. Test rate limiting (429 responses). Test 20-model limit. Test 404 for non-existent/unauthorized models. Test masked API key in list response. Test partial update semantics (probe triggered only on connection field changes).
  - **Dependencies**: Phase 2 complete
  - **Files**: `tests/test_api_custom_models.py` (new)
  - **Acceptance**: All endpoints tested; error responses match spec schemas; security validations verified

### 6.2: Integration Tests

- [x] **Task 6.5**: Integration test for add → test → assign → generate flow
  - **Description**: End-to-end flow: create model via API → trigger capability test → accept suggested roles → verify model appears in model-options → select in generation page → verify custom model used in generation. Test with mocked model endpoint (httpresponses or test server).
  - **Dependencies**: Phase 2, Phase 4
  - **Files**: `tests/test_integration_custom_models.py` (new)
  - **Acceptance**: Full lifecycle tested; custom model used in generation; SSE includes `custom_model_id`

- [x] **Task 6.6**: Integration test for data migration
  - **Description**: Create test data in `user_custom_audit_models`, run migration, verify data in `user_custom_models` matches expected mapping. Verify old table data preserved. Verify backward compatibility (old `get_by_user_id()` still works).
  - **Dependencies**: Task 1.2
  - **Files**: `tests/test_migration_custom_models.py` (new)
  - **Acceptance**: Migration verified with sample data; no data loss; old endpoint functional; `status='validated'` preserved

- [x] **Task 6.7**: Integration test for generation page model resolution
  - **Description**: Verify model resolution logic: select custom model → backend resolves to custom endpoint → generation uses custom base_url/key. Test fallback to platform default when custom model fails. Test all five roles. Test vision request with custom model (multimodal format).
  - **Dependencies**: Task 4.2
  - **Files**: `tests/test_generation_custom_models.py` (new)
  - **Acceptance**: Custom model resolution correct for all roles; fallback works; vision multimodal request correct

- [x] **Task 6.8**: Integration test for audit model fallback compatibility
  - **Description**: Test ContentAuditor checks new `user_custom_models` first, falls back to old table. Test when both exist (new takes precedence). Test when only old exists (still works). Test migration copies audit data with correct `assigned_roles`.
  - **Dependencies**: Task 4.3
  - **Files**: `tests/test_audit_custom_models.py` (new)
  - **Acceptance**: Audit resolution precedence verified; backward compatibility maintained; migration preserves audit data

### 6.3: Frontend Tests

- [x] **Task 6.9**: Frontend component render and interaction tests
  - **Description**: Test CustomModelsManager renders model list correctly. Test AddModelDialog form validation. Test ModelCard displays badges, actions. Test TestResultPanel shows per-capability results. Test delete confirmation dialog. Test empty state. Test loading skeletons.
  - **Dependencies**: Phase 3
  - **Files**: `frontend/src/components/__tests__/` (new directory)
  - **Acceptance**: Components render without errors; form validation triggers; action buttons call correct handlers; empty/loading states display

- [x] **Task 6.10**: Frontend API client error handling tests
  - **Description**: Test typed error responses from API client functions. Test 422 validation errors parsed correctly. Test 404 handling. Test 429 rate limit handling. Test network error fallback.
  - **Dependencies**: Task 3.7
  - **Files**: `frontend/src/__tests__/api.test.ts` (new)
  - **Acceptance**: All error types handled; typed errors accessible; user-friendly error messages displayed

### 6.4: Manual Testing

- [ ] **Task 6.11**: Manual testing checklist
  - **Description**: Complete manual testing checklist:
    - [ ] Add model with single model_id
    - [ ] Add model with multiple model_ids (comma-separated)
    - [ ] Test capabilities (text, vision, embedding)
    - [ ] Assign roles to model
    - [ ] Use custom model in generation page
    - [ ] Edit existing model (name only, no re-probe)
    - [ ] Edit existing model (base_url change, triggers re-probe)
    - [ ] Delete model (with confirmation)
    - [ ] Verify dropdown shows custom models with visual badge
    - [ ] Test backward compatibility (old single-model config still works via old endpoint)
    - [ ] Test SSRF URL rejection with localhost/private IP
    - [ ] Test rate limiting (10 creations/hour, 5 tests/model/hour)
    - [ ] Test max model limit (21st model rejected)
    - [ ] Test quota switch shows custom models as alternatives
  - **Dependencies**: All phases complete
  - **Files**: N/A (manual process)
  - **Acceptance**: All 14 checklist items pass on both zh and en locales

---

## Phase 7: Documentation & Deployment

- [x] **Task 7.1**: Update backend API documentation
  - **Description**: Document all new endpoints with request/response schemas, authentication requirements, rate limits, and error codes. Add to existing API docs or create inline FastAPI OpenAPI annotations with detailed descriptions and examples.
  - **Dependencies**: Phase 2
  - **Files**: `server.py` (docstrings/OpenAPI tags), or `docs/api.md` (if exists)
  - **Acceptance**: All 6 new endpoints documented with examples; OpenAPI schema updated

- [x] **Task 7.2**: Update frontend component documentation
  - **Description**: Add JSDoc comments to new components and API functions. Document props, state, and event handlers. Add usage examples for `CustomModelsManager` integration.
  - **Dependencies**: Phase 3
  - **Files**: `frontend/src/components/CustomModelsManager.tsx`, related components
  - **Acceptance**: Components have JSDoc; props documented; usage examples in comments

- [x] **Task 7.3**: Create user-facing feature documentation
  - **Description**: Add multi-model management feature description to project README or user docs. Explain how to add models, test capabilities, assign roles, and use in generation. Include screenshots once UI is finalized.
  - **Dependencies**: All implementation phases
  - **Files**: `README.md` (add section), or `docs/features/multi-model.md` (new)
  - **Acceptance**: User-facing documentation clear and complete; covers full lifecycle (add → test → assign → use)

- [x] **Task 7.4**: Create migration guide for existing users
  - **Description**: Document migration from single-model configuration to multi-model system. Explain automatic migration behavior, backward compatibility of old endpoints, and how to verify data migrated correctly. Include rollback instructions if needed.
  - **Dependencies**: Task 1.2
  - **Files**: `docs/migration-guide-v2.md` (new)
  - **Acceptance**: Migration guide covers automatic migration, data verification steps, rollback plan, and old endpoint deprecation timeline

- [ ] **Task 7.5**: Tag release version
  - **Description**: Tag as v2.0.0 (major version bump for breaking change: data model migration, deprecated endpoints, component replacement). Update CHANGELOG.md with new features, breaking changes, and migration notes.
  - **Dependencies**: All phases complete and tested
  - **Files**: `CHANGELOG.md`, git tag
  - **Acceptance**: Version tagged; CHANGELOG updated; migration guide linked

---

## Dependency Graph

```
Phase 1 (DB Schema)
  ├── Task 1.1 (create table)
  │   ├── Task 1.2 (migration)
  │   └── Task 1.3 (CRUD methods)
  └── Task 1.4 (encryption helpers)

Phase 2 (Backend API)
  ├── Task 2.5 (probe function) ← depends on 1.4
  │   └── Tasks 2.7, 2.8, 2.9 (capability probes) ← depend on 1.4
  │       └── Task 2.6 (test endpoint) ← depends on 2.7, 2.8, 2.9
  │           └── Task 2.10 (role suggestions)
  ├── Task 2.1 (GET list) ← depends on 1.3
  ├── Task 2.2 (POST create) ← depends on 1.3, 2.5
  ├── Task 2.3 (PUT update) ← depends on 1.3, 2.5
  │   └── Task 2.12 (manual override) ← depends on 2.3
  ├── Task 2.4 (DELETE) ← depends on 1.3
  └── Task 2.11 (assign endpoint) ← depends on 1.3

Phase 3 (Frontend)
  ├── Tasks 3.3, 3.4, 3.5, 3.6 (leaf components)
  │   └── Task 3.2 (ModelList) ← depends on 3.3
  │       └── Task 3.1 (CustomModelsManager) ← depends on 3.2, 3.3, 3.4
  ├── Task 3.7 (API client), Task 3.8 (types), Task 3.9 (i18n)
  └── Task 3.10 (SettingsPage integration) ← depends on 3.1

Phase 4 (Generation Integration)
  ├── Task 4.1 (provider_registry merge) ← depends on 1.3, 2.6
  │   └── Task 4.4 (frontend dropdowns) ← depends on 4.1
  │       └── Task 4.5 (quota switch) ← depends on 4.2
  ├── Task 4.2 (model resolution) ← depends on 1.3, 1.4
  ├── Task 4.3 (audit fallback) ← depends on 1.2, 1.3
  └── Task 4.6 (frontend caching) ← depends on 3.1

Phase 5 (Security) - can run in parallel with Phases 2-4
Phase 6 (Testing) - runs after each phase is complete
Phase 7 (Docs/Deploy) - runs after all testing passes
```

---

## Estimated Effort

| Phase | Tasks | Estimated Days |
|-------|-------|---------------|
| Phase 1: DB Schema & Migration | 4 | 2-3 |
| Phase 2: Backend API | 12 | 6-8 |
| Phase 3: Frontend Components | 10 | 5-7 |
| Phase 4: Generation Integration | 6 | 3-4 |
| Phase 5: Security & Validation | 5 | 2-3 |
| Phase 6: Testing | 11 | 4-5 |
| Phase 7: Docs & Deployment | 5 | 2-3 |
| **Total** | **53 tasks** | **24-33 days** |

---

## Notes

- **Breaking change**: This is a major version upgrade (v2.0.0). Existing `user_custom_audit_models` data will be auto-migrated. Old endpoints remain functional but deprecated.
- **Design system**: All new UI components follow the cyberpunk design system (`signal-cyan`, `night-900` palette). Reference `xiangmushu-design-taste` skill for styling consistency.
- **i18n**: All new strings in both Chinese (zh) and English (en). No hardcoded strings in components.
- **Performance**: Custom model resolution adds one DB query per generation request. Cached per session to avoid repeated lookups.
- **No new frontend pages**: Integration modifies existing components (SettingsPage, GeneratePage dropdowns) — no new page-level components created in the generation page.
