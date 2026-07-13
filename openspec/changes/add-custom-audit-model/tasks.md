## 1. Database Schema

- [x] 1.1 Add MySQL migration `migrations/mysql/005_user_custom_audit_models.sql` creating the `user_custom_audit_models` table with columns: `id BIGINT PK AUTO_INCREMENT`, `user_id BIGINT NOT NULL UNIQUE FK → users(id) ON DELETE CASCADE`, `name VARCHAR(64)`, `base_url VARCHAR(512)`, `model_id VARCHAR(128)`, `encrypted_api_key TEXT`, `api_key_hint VARCHAR(32)`, `status VARCHAR(16)`, `validated_at TIMESTAMP`, `created_at TIMESTAMP`, `updated_at TIMESTAMP`
- [x] 1.2 Add equivalent inline DDL in `core/db.py` (or wherever the SQLite inline schema lives) so the same table is created automatically for SQLite persistence mode
- [x] 1.3 Add a dataclass `UserCustomAuditModel` in `core/custom_audit.py` with typed fields matching the table

## 2. Backend: Cryptography & Core Module

- [x] 2.1 Create `core/custom_audit.py` module with dataclass + CRUD helpers: `get_by_user_id(db, user_id) -> UserCustomAuditModel | None`, `save(db, user_id, name, base_url, model_id, encrypted_api_key, api_key_hint, status, validated_at) -> UserCustomAuditModel`, `delete_by_user_id(db, user_id) -> bool`
- [x] 2.2 Implement `_encrypt_api_key(plaintext: str) -> str` using the existing `core.billing.encrypt_api_key` helper (do NOT re-implement Fernet here)
- [x] 2.3 Implement `_decrypt_api_key(ciphertext: str) -> str` using `core.billing.decrypt_api_key`
- [x] 2.4 Implement `_build_key_hint(api_key: str) -> str` returning first-4 + "…" + last-4 (or equivalent pattern used by billing preview)

## 3. Backend: URL Validation (SSRF Protection)

- [x] 3.1 Implement `validate_base_url(url_str: str) -> tuple[bool, str]` in `core/custom_audit.py` that parses the URL, rejects empty/non-parseable/non-`http`/`https` schemes with a structured `url_format` error code
- [x] 3.2 Implement SSRF block-list check rejecting resolved hostnames/IPs in: `localhost`, `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`, `::1`, and any link-local range — returning `ssrf_rejected` error code
- [x] 3.3 Resolve the hostname to an IP (via `socket.getaddrinfo`) BEFORE issuing any probe HTTP call, and reject based on resolved IP rather than raw hostname string

## 4. Backend: Probe Integration

- [x] 4.1 Modify `core/api_key_validation.py`'s `probe_api_key_model` (or `_base_url_for_provider`) to accept an optional `base_url_override: str | None = None` parameter; when provided, bypass the provider-registry base_url lookup and use the override directly for the OpenAI client
- [x] 4.2 Implement `probe_custom_model(name, base_url, model_id, api_key) -> ProbeResult` in `core/custom_audit.py` that: (a) runs `validate_base_url` (rejects if URL/SSRF-invalid), (b) calls `probe_api_key_model(api_key, model_id, base_url_override=base_url)`, (c) normalizes errors into the structured `{error_kind, error_detail}` form used by the endpoint
- [x] 4.3 Ensure plaintext api_key is never written to logger output at any log level inside `probe_custom_model`

## 5. Backend: REST Endpoints

- [x] 5.1 Add `GET /api/user/custom-audit-model` to `server.py` under the existing bearer-auth dependency. Returns `{id, name, base_url, model_id, api_key_preview, status, validated_at, created_at, updated_at}` on 200; returns `404 {"error":{"code":"no_custom_audit_model"}}` when no record exists
- [x] 5.2 Add `POST /api/user/custom-audit-model` to `server.py` accepting body `{name, base_url, model_id, api_key}`. On successful probe: encrypt + persist + return `200` with the serialized record (api_key redacted). On probe failure: return `422 {"error":{"code":"<kind>","message":"<localized detail>"}}` where `code` is one of `url_format` / `ssrf_rejected` / `auth` / `network` / `timeout` / `model_not_found` / `bad_response`
- [x] 5.3 Add `DELETE /api/user/custom-audit-model` to `server.py`. Return `204` whether a record existed or not (idempotent)
- [x] 5.4 Localize the `error_detail` strings using the existing i18n resolution path — respect `Accept-Language` header, default to `zh`
- [x] 5.5 Update `SUPPORTED_API_KEY_PROVIDERS` handling (if the new endpoint shares validation code paths) OR ensure the new endpoint bypasses the provider whitelist entirely (since this is NOT a provider key)

## 6. Backend: Content Auditor Integration

- [x] 6.1 Add `_resolve_audit_client(self)` method to `core/content_auditor.py`'s `ContentAuditor` class that: (a) calls `get_by_user_id(db, self.user_id)`, (b) if a `validated` record exists, returns `(OpenAI(api_key=decrypt(...), base_url=..., timeout=30, max_retries=1), model_id, True)` (the `True` = "used_custom"), otherwise returns the existing default client path with `False`
- [x] 6.2 Wrap each content-audit LLM call in the segment audit path with try/except: on exception AND `used_custom=True`, log a warning (no plaintext key), emit a fallback event dict, then retry with the default `AUDIT_TEXT_MODEL` client using the existing default credential chain
- [x] 6.3 Shape fallback events as `{segment_index: int, custom_model_id: str, fallback_model_id: str, error_kind: str, error_detail: str, occurred_at: str (ISO timestamp)}`
- [x] 6.4 Cache the resolved custom client on the `ContentAuditor` instance across segments within a single generation session (so we don't re-hit the DB per segment) — invalidate cache only if the user's record status changes during the session
- [x] 6.5 Ensure the existing non-custom-model code path is byte-identical when no custom model is configured (zero regression risk)

## 7. Backend: Generation Session Aggregation

- [x] 7.1 Modify the generation endpoint (both `/api/generate` and `/api/generate/sessions` paths) to collect all per-segment `fallback_event` dicts into a session-level `audit_fallback_events: list` field
- [x] 7.2 Include `audit_fallback_events: [...]` in the `/done` SSE event payload
- [x] 7.3 For streaming: emit an inline `{type: "audit_fallback", ...}` event at the moment the fallback occurs within the stream (duplicated in the `/done` event — consistent with existing pattern for `audit` events)
- [x] 7.4 Add a backend unit test (in `tests/` or extend `smoke_test_models.py --offline`) that simulates a custom model probe success + runtime failure, asserts that the fallback event is recorded and the final segment verdict comes from the default-model retry

## 8. Frontend: Settings Card

- [x] 8.1 Add a new component `CustomAuditModelCard.tsx` (or include inline in `SettingsPage.tsx`) positioned below the existing 3-provider card grid
- [x] 8.2 The card SHALL have four inputs: `name` (text, placeholder localized), `base_url` (text, placeholder `https://...`), `model_id` (text), `api_key` (password input, shows preview when loaded from GET)
- [x] 8.3 Card fetches `GET /api/user/custom-audit-model` on mount; pre-fills inputs if present; shows empty form with 禁用 删除 button if 404
- [x] 8.4 "测试并保存" button POSTs with `{name, base_url, model_id, api_key}`; renders inline 422 error (localized `error_detail`) beneath the form; on 200 refreshes the card and updates the status badge + `validated_at` timestamp
- [x] 8.5 "删除" button calls DELETE; clears the form; re-fetches GET; disables itself on 404
- [x] 8.6 Disable both action buttons while a request is in flight (busy state); show a `<Loader2>` spinner inline
- [x] 8.7 Password-mask toggle (eye icon) for the api_key input — standard pattern used elsewhere in the codebase

## 9. Frontend: Fallback Banner in Generate Results

- [x] 9.1 Modify the existing generation "运行概览" (RunOverview) component to inspect the session's `audit_fallback_events` list
- [x] 9.2 When the list is non-empty, render a non-blocking warning banner (NOT error, NOT toast) with: custom model name, aggregated count ("本次有 N 次审核调用失败"), default model id, first-occurring `error_kind` + truncated `error_detail` (80 chars), and a "前往设置" link to `/settings#custom-audit-model`
- [x] 9.3 The banner SHALL NOT block viewing/downloading the document, and SHALL NOT trigger any toast or email
- [x] 9.4 The banner SHALL be scoped to this generation session — NOT persisted across sessions

## 10. i18n Keys

- [x] 10.1 Add all new Settings card strings to `frontend/src/i18n.ts` under both `zh` and `en`: `settings.customAudit.title`, `.description`, `.namePlaceholder`, `.baseUrlPlaceholder`, `.modelIdPlaceholder`, `.apiKeyPlaceholder`, `.saveButton`, `.deleteButton`, `.validated`, `.failed`, `.untested`, `.testedAt`, `.busy`, `.saveError`, `.deleteError`, `.introHint`
- [x] 10.2 Add all new generate banner strings: `generate.fallbackBanner.title`, `.body`, `.goToSettings`, `.defaultModel`, `.errorCount`
- [x] 10.3 Add localized error keys used by POST endpoint 422 responses (zh + en): `errors.customAudit.url_format`, `.ssrf_rejected`, `.auth`, `.network`, `.timeout`, `.model_not_found`, `.bad_response`

## 11. Verification

- [ ] 11.1 Run `npm run build` in `frontend/` — must pass `tsc --noEmit && vite build` cleanly
- [ ] 11.2 Run `pytest tests/` (or `smoke_test_models.py --offline` + the new test from 7.4) — must all pass
- [ ] 11.3 Manual: configure a valid OpenAI-compatible model (e.g. DashScope itself at a different model id like `qwen3.6-flash` on a separate api key) and run a generation; verify the custom model is hit for audit, no fallback banner shown
- [ ] 11.4 Manual: configure a model with an invalid api_key; verify POST returns 422 with localized error and no record is saved
- [ ] 11.5 Manual: configure a valid model that fails at runtime (e.g. a mock base_url that returns 500); verify generation still succeeds using the default model, the fallback banner is displayed with correct count + error
- [ ] 11.6 Manual: verify SSRF protection — POST with `base_url=http://169.254.169.254/latest/meta-data/` must be rejected with `ssrf_rejected` without any probe HTTP request being issued
- [ ] 11.7 Manual: verify i18n — switch settings language to English; Settings card + fallback banner + API error messages all render correctly without hardcoded Chinese

## 12. Documentation & Deployment

- [ ] 12.1 Add a brief note to `docs/` (or `CHANGELOG.md`) describing the new capability for release notes
- [ ] 12.2 Verify the new migration runs cleanly on the production MySQL (`systemctl restart xiangmushu` after pull); confirm `mysql -e "DESCRIBE user_custom_audit_models"` shows expected schema
- [ ] 12.3 After deploy, run the `scripts/verify-after-deploy.cjs` full audit to ensure no design-system regression was introduced
