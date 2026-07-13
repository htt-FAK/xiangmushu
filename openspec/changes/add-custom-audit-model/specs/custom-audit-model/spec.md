# Custom Audit Model — Specification

## ADDED Requirements

### Requirement: Settings page exposes custom audit model configuration card
The system SHALL render a "自定义内容审核模型" configuration card inside the `/settings` page for every authenticated user, positioned below the existing three fixed provider cards (dashscope / deepseek / mimo).

#### Scenario: Authenticated user opens Settings page
- **WHEN** an authenticated user navigates to `/settings`
- **THEN** the page SHALL render the custom audit model card alongside the three fixed provider cards
- **AND** the card SHALL display four inputs: 显示名称 (name), Base URL, Model ID, API Key (password-masked, revealing first-4 + last-4 characters when a saved key preview exists) and two action buttons: 测试并保存 and 删除
- **AND** the card SHALL display validation status feedback: one of `untested` / `validated` / `failed`, with a status badge and (if validated) the last validation timestamp

#### Scenario: User views an empty configuration
- **WHEN** the authenticated user has never saved a custom audit model
- **THEN** the card SHALL render empty inputs
- **AND** the 删除 button SHALL be disabled
- **AND** the status area SHALL display an introductory hint localized in the current language

#### Scenario: User views an existing configuration
- **WHEN** the authenticated user has a saved custom audit model
- **THEN** the card SHALL prefill the name, base_url, and model_id inputs with existing values
- **AND** the api_key input SHALL be pre-filled with the preview form (e.g. `sk-xxx…abcd`) rather than the raw secret
- **AND** the 删除 button SHALL be enabled
- **AND** the status area SHALL display the current validation status badge and the `validated_at` timestamp (if validated)

### Requirement: Configuration save requires test-time model probe
The system SHALL probe the user-submitted custom audit model by sending a minimal chat completion request to the user's base_url before persisting the configuration; on probe failure the save SHALL be rejected without writing any data.

#### Scenario: User submits configuration and probe succeeds
- **WHEN** the authenticated user POSTs `/api/user/custom-audit-model` with `{name, base_url, model_id, api_key}` and the model successfully responds to the probe request `{"system":"Return OK.","user":"Reply with OK only."}` (max_tokens=8, temperature=0) within the configured timeout
- **THEN** the system SHALL encrypt the api_key at rest, persist the record, set status to `validated`, record `validated_at` as the current timestamp, and return the persisted configuration (api_key redacted)
- **AND** future generation sessions for this user SHALL use this custom audit model for content audit

#### Scenario: User submits configuration and probe fails
- **WHEN** the authenticated user POSTs `/api/user/custom-audit-model` with a payload whose probe request returns a non-success response, raises an exception, or times out
- **THEN** the system SHALL return HTTP 422 with a structured error body including `error_kind` (one of: `auth` / `network` / `timeout` / `model_not_found` / `bad_response` / `invalid_url`) and a human-readable `error_detail` localized in the user's language
- **AND** the system SHALL NOT persist any configuration record for this user based on this failed save attempt
- **AND** any previously saved valid configuration for this user SHALL remain untouched

#### Scenario: User submits configuration with invalid URL
- **WHEN** the authenticated user POSTs `/api/user/custom-audit-model` with a `base_url` that is empty, not a parseable URL, or uses a disallowed scheme (anything other than `http` / `https`)
- **THEN** the system SHALL return HTTP 422 with `error_kind: url_format` and localized error detail
- **AND** no probe request SHALL be issued

#### Scenario: User submits configuration with SSRF-disallowed URL
- **WHEN** the authenticated user POSTs `/api/user/custom-audit-model` with a `base_url` targeting a disallowed network (e.g. `localhost`, `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`, `::1`, or any link-local address)
- **THEN** the system SHALL return HTTP 422 with `error_kind: ssrf_rejected`
- **AND** no probe request SHALL be issued

### Requirement: Configuration read endpoint exposes redacted state
The system SHALL expose `GET /api/user/custom-audit-model` returning the current user's configuration (if any), with the api_key redacted and replaced by a preview (first-4 + last-4 characters).

#### Scenario: User has no saved configuration
- **WHEN** the authenticated user has no saved custom audit model
- **THEN** the endpoint SHALL return HTTP 404 with a stable error code `no_custom_audit_model`

#### Scenario: User has a saved configuration
- **WHEN** the authenticated user has a saved custom audit model
- **THEN** the endpoint SHALL return HTTP 200 with `{id, name, base_url, model_id, api_key_preview, status, validated_at, created_at, updated_at}`
- **AND** the api_key field SHALL contain only the preview form, never the raw secret

### Requirement: Configuration delete reverts to default audit model
The system SHALL expose `DELETE /api/user/custom-audit-model` which removes the current user's custom audit model record and causes all subsequent generations to use the platform default `AUDIT_TEXT_MODEL`.

#### Scenario: User deletes an existing configuration
- **WHEN** the authenticated user has a saved custom audit model and calls DELETE
- **THEN** the system SHALL hard-delete the record (including the encrypted api_key)
- **AND** subsequent generation sessions for this user SHALL fall back to the default `AUDIT_TEXT_MODEL` path

#### Scenario: User deletes when no configuration exists
- **WHEN** the authenticated user has no saved custom audit model and calls DELETE
- **THEN** the system SHALL return HTTP 204 with no body and the user's generation behavior SHALL remain unchanged

### Requirement: API key is encrypted at rest using the existing Fernet infrastructure
The system SHALL encrypt the custom audit model api_key using the existing `core/billing.encrypt_api_key()` primitive and decrypt using `decrypt_api_key()`; the plaintext api_key SHALL never appear in any log, database column, or HTTP response body outside the save-request path.

#### Scenario: Saving records the api_key
- **WHEN** the POST endpoint persists a custom audit model record
- **THEN** the `encrypted_api_key` column SHALL contain only the ciphertext produced by `encrypt_api_key(api_key)`
- **AND** the response body SHALL contain `api_key_preview`, never the plaintext

#### Scenario: Reading records the api_key
- **WHEN** the GET endpoint serializes a record
- **THEN** the plaintext api_key SHALL be decrypted only transiently to compute the first-4 + last-4 preview, then discarded
- **AND** the response body SHALL NOT contain the plaintext api_key

#### Scenario: Application logs
- **WHEN** any application log entry refers to a custom audit model record (save / read / delete / probe)
- **THEN** the log message SHALL NOT include the plaintext api_key

### Requirement: Content audit transparently routes through custom model when configured
The system SHALL, for every generation segment, attempt to use the user's validated custom audit model as the primary auditor, falling back to the platform default `AUDIT_TEXT_MODEL` if the custom model fails at runtime.

#### Scenario: User has validated custom model and custom model call succeeds
- **WHEN** a generation segment invokes the content auditor for an authenticated user who has a `validated` custom audit model, and the custom model call completes without raising
- **THEN** the auditor SHALL use the user's custom base_url + api_key + model_id for the call
- **AND** no fallback event SHALL be recorded

#### Scenario: User has validated custom model but custom model call fails at runtime
- **WHEN** a generation segment invokes the content auditor for an authenticated user who has a `validated` custom audit model, and the custom model call raises an exception (network, timeout, auth, bad response, etc.)
- **THEN** the auditor SHALL emit a fallback event with `{segment_index, custom_model_id, fallback_model_id, error_kind, error_detail, occurred_at}`, where `fallback_model_id` is the configured default `AUDIT_TEXT_MODEL`
- **AND** the auditor SHALL immediately retry the same segment's audit using the default `AUDIT_TEXT_MODEL` with the same user credential chain that was in effect before this change
- **AND** the retry's verdict SHALL be the verdict returned to the caller
- **AND** the exception MUST NOT propagate to the generation pipeline
- **AND** the generation segment's per-segment audit return object SHALL include the fallback event list

#### Scenario: User has no custom model configured
- **WHEN** a generation segment invokes the content auditor for an authenticated user who has no custom audit model record
- **THEN** the auditor SHALL behave identically to the pre-change implementation (use the configured default `AUDIT_TEXT_MODEL` path)
- **AND** no fallback event SHALL be recorded

#### Scenario: User has untested or failed-status custom model
- **WHEN** a generation segment invokes the content auditor for an authenticated user whose custom audit model record has status `untested` or `failed`
- **THEN** the auditor SHALL behave as if no custom model is configured (use the default `AUDIT_TEXT_MODEL` path)
- **AND** no fallback event SHALL be recorded

### Requirement: Generation session aggregates fallback events across all segments
The system SHALL aggregate all per-segment audit fallback events into the generation session response payload under the field `audit_fallback_events` (list).

#### Scenario: Session with zero fallbacks
- **WHEN** a generation session completed with no runtime audit fallback
- **THEN** the session's `/done` event SHALL include `audit_fallback_events: []`

#### Scenario: Session with N fallbacks
- **WHEN** a generation session completed and K segments across N segments triggered runtime audit fallback
- **THEN** the session's `/done` event SHALL include `audit_fallback_events` containing K entries, ordered by `segment_index`

#### Scenario: Streaming clients receive fallback events inline
- **WHEN** a generation segment triggers a runtime audit fallback and is being streamed to the frontend
- **THEN** the stream SHALL emit an inline `{type: "audit_fallback", ...}` event at the moment the fallback occurs, with the same fields as the session-level `audit_fallback_events` entry

### Requirement: Generation results UI surfaces weak-notification fallback banner (Plan B)
The generate page SHALL render a non-blocking notification banner listing aggregated fallback info when the generation session recorded at least one audit fallback event.

#### Scenario: Session with no fallback events
- **WHEN** a generation session completes and `audit_fallback_events` is empty
- **THEN** the generate results page SHALL NOT render any fallback banner

#### Scenario: Session with fallback events
- **WHEN** a generation session completes with non-empty `audit_fallback_events`
- **THEN** the "运行概览" (Run Overview) panel SHALL render a non-blocking banner containing:
  - the custom model's display name
  - the aggregated fallback count (total segments affected)
  - the default model id that was used as fallback
  - the first-occurring `error_kind` + short `error_detail` (truncated to 80 characters)
  - a localized "前往设置" action that navigates to `/settings#custom-audit-model`
- **AND** the banner SHALL be styled as a warning (not error) — it SHALL NOT block the user from viewing or downloading the generated document
- **AND** the banner SHALL NOT trigger any toast, popup, or email notification

#### Scenario: User dismisses or ignores banner
- **WHEN** the fallback banner is rendered
- **THEN** the user SHALL be able to proceed to download the document or start a new generation without being blocked by the banner
- **AND** the banner's presence SHALL NOT persist across future generation sessions (it is tied to a single generation session's response)

### Requirement: All new user-visible strings are added to both zh and en dictionaries
The system SHALL add i18n keys for every user-facing string introduced by this change, in both the `zh` and `en` dictionaries of `frontend/src/i18n.ts`, and SHALL NOT ship any hardcoded Chinese or English text in new JSX or JSX-adjacent code.

#### Scenario: Settings card strings
- **WHEN** the Settings page renders the custom audit model card
- **THEN** every label, placeholder, button text, status badge text, and hint text SHALL come from the i18n dictionary
- **AND** the card SHALL render correctly in both `zh` and `en` without code changes

#### Scenario: Generate fallback banner strings
- **WHEN** the generate page renders the fallback banner
- **THEN** the banner title, body, error summary prefix, and action link text SHALL come from the i18n dictionary
- **AND** the banner SHALL render correctly in both `zh` and `en`

#### Scenario: API error messages
- **WHEN** the POST endpoint returns a 422 validation error
- **THEN** the body's `error_detail` field SHALL be localized based on the `Accept-Language` header (defaulting to `zh`), using the same i18n resolution rules as other backend-generated user-facing messages
