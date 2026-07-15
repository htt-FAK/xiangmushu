# Model Capability Testing

## Overview

Automatically probe custom AI models to detect their capabilities (text generation, vision/multimodal understanding, text embeddings) and produce role assignment recommendations. The testing system sends targeted requests to each model endpoint, evaluates responses, and returns structured capability tags with suggested system roles. Test results are cached to avoid redundant API calls, and users can manually override detected capabilities.

## Requirements

### Requirement 1: Auto-detect text generation capability

- **Description**: The system sends a minimal text generation request to the model to verify it can produce text output.
- **Acceptance Criteria**:
  - System sends a `POST /chat/completions` request with a simple prompt: `"Say hello in one sentence."` using the model's `default_model_id`
  - System validates the response contains a non-empty `choices[0].message.content` string
  - Text test uses a 30-second timeout
  - On success, `"text"` is added to the model's `capabilities` array
  - On failure (timeout, non-200 response, empty content, malformed JSON), `"text"` is NOT added and the failure reason is recorded in `last_error`

### Requirement 2: Auto-detect vision capability

- **Description**: The system sends a vision/multimodal request to determine if the model can process image inputs.
- **Acceptance Criteria**:
  - System sends a `POST /chat/completions` request with a small embedded test image (base64-encoded 10x10 solid-color PNG, ~100 bytes) and prompt: `"Describe the color of this image in one word."`
  - The request uses the OpenAI-compatible `content` array with `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}`
  - Vision test uses a 60-second timeout
  - System validates the response contains a non-empty `choices[0].message.content` string
  - On success, `"vision"` is added to capabilities
  - On failure (including model returning 400/422 for unsupported image input), `"vision"` is NOT added and the specific reason (e.g., "model does not support image input") is recorded

### Requirement 3: Auto-detect embedding capability

- **Description**: The system sends an embedding request to determine if the model can produce vector representations of text.
- **Acceptance Criteria**:
  - System sends a `POST /embeddings` request with input text: `"Test embedding for capability detection."`
  - The embedding model name is derived from the model entry's `model_id` field (first ID if comma-separated); the system also attempts `text-embedding-` prefixed variants if the primary model ID fails
  - Embedding test uses a 30-second timeout
  - System validates the response contains a non-empty `data[0].embedding` array with numeric values
  - On success, `"embedding"` is added to capabilities
  - On failure (endpoint missing, model not compatible, timeout), `"embedding"` is NOT added

### Requirement 4: Unified test endpoint

- **Description**: A single API endpoint triggers capability tests for one model, optionally scoped to specific capability types.
- **Acceptance Criteria**:
  - `POST /api/user/custom-models/{id}/test` accepts optional `test_types` array (subset of `["text", "vision", "embedding"]`); defaults to all three
  - All requested tests run sequentially (not in parallel) to respect rate limits
  - Response includes: model `id`, detected `capabilities` array, computed `suggested_roles` array, `status` (`"tested"` or `"untested"` if all failed), `last_tested_at` timestamp, and `last_error` (first failure reason, or `null`)
  - The model's `capabilities` and `last_tested_at` fields are persisted in the database after the test
  - If the model's `api_key` is invalid (probe returns auth error), the entire test is rejected with 422 and no partial results are saved

### Requirement 5: Role suggestion logic

- **Description**: Based on detected capabilities, the system computes and returns recommended role assignments.
- **Acceptance Criteria**:
  - `text` capability → suggests `text-gen` role
  - `vision` capability → suggests `vision` role
  - `embedding` capability → suggests `embedding` role
  - `text` capability (standalone) → may also suggest `audit` role if the model name or model ID contains terms like "qwen", "gpt", "claude", "deepseek" (indicating a general-purpose LLM)
  - `text` capability → may also suggest `small-llm` role if the model ID contains "small", "mini", "turbo", or similar lightweight indicators
  - Multiple suggested roles are returned in order of confidence: `["text-gen", "vision", "embedding", "audit", "small-llm"]`
  - User is not forced to accept suggestions — suggestions are advisory only

### Requirement 6: Manual capability override

- **Description**: Users can manually override auto-detected capabilities through the edit interface.
- **Acceptance Criteria**:
  - The `PUT /api/user/custom-models/{id}` endpoint accepts an optional `capabilities` field (array of `"text"`, `"vision"`, `"embedding"`)
  - When manually set, the `capabilities` field overrides auto-detected values
  - The `status` field changes to `"override"` when capabilities are manually set (distinct from `"tested"` for auto-detected)
  - Frontend clearly distinguishes auto-detected capabilities (with a "Auto" label) from manually overridden capabilities (with a "Manual" label)
  - System does not re-test capabilities unless the user explicitly triggers a new test via the test endpoint
  - Test results panel shows both the auto-detected and manually overridden states

### Requirement 7: Error handling and retry

- **Description**: Test failures are handled gracefully with clear error messages, and users can retry failed tests.
- **Acceptance Criteria**:
  - Each capability test is independent — a failure in one test does not block other tests
  - Partial success is normal (e.g., text works but vision fails) and saved as-is
  - `last_error` stores the FIRST encountered error message and corresponding test type (e.g., `"vision: connection timeout after 60s"`)
  - Frontend displays per-capability test results: green checkmark for passed, red X for failed, gray dash for skipped
  - "Retry" button re-triggers the test for the specific failed capability (or all capabilities)
  - "Test All" button is always available regardless of current status
  - Network errors, invalid credentials, and malformed responses each produce distinct, localized error messages
  - Failed tests do not block the user from editing or using the model for roles that don't require the failed capability

### Requirement 8: Test result caching

- **Description**: Test results are cached to avoid repeated API calls for unchanged models.
- **Acceptance Criteria**:
  - Test results are persisted in the `user_custom_models` table (`capabilities`, `last_tested_at`, `last_error` fields)
  - Frontend caches test results in `localStorage` with a 5-minute TTL keyed by model ID
  - The "Test" button shows a "Re-test" label when `last_tested_at` is within 5 minutes, and "Test" when older or never tested
  - Backend does not enforce caching — repeated test requests always execute fresh tests
  - Cache is invalidated when model configuration (base_url, model_id, or api_key) changes

## API Specification

### Endpoint: POST /api/user/custom-models/{id}/test

**Headers**: `Authorization: Bearer <jwt>`, `Content-Type: application/json`

**Request:**
```json
{
  "test_types": ["text", "vision", "embedding"]
}
```

`test_types` is optional. If omitted or empty, all three tests run.

---

**Response (200, all tests passed):**
```json
{
  "id": 1,
  "capabilities": ["text", "vision", "embedding"],
  "status": "tested",
  "last_tested_at": "2026-07-14T10:30:00Z",
  "last_error": null,
  "suggested_roles": ["text-gen", "vision", "embedding"],
  "test_results": {
    "text": { "passed": true, "latency_ms": 1234, "detail": null },
    "vision": { "passed": true, "latency_ms": 3456, "detail": null },
    "embedding": { "passed": true, "latency_ms": 567, "detail": null }
  }
}
```

---

**Response (200, partial failure):**
```json
{
  "id": 2,
  "capabilities": ["text"],
  "status": "tested",
  "last_tested_at": "2026-07-14T10:30:00Z",
  "last_error": "vision: model returned 422 - image input not supported",
  "suggested_roles": ["text-gen", "audit"],
  "test_results": {
    "text": { "passed": true, "latency_ms": 890, "detail": null },
    "vision": { "passed": false, "latency_ms": 2100, "detail": "model returned 422 - image input not supported" },
    "embedding": { "passed": false, "latency_ms": 150, "detail": "endpoint /embeddings returned 404" }
  }
}
```

---

**Response (422, auth failure — entire test rejected):**
```json
{
  "error": {
    "code": "auth",
    "message": "API key is invalid or expired. Please update the model configuration."
  }
}
```

---

**Response (404):**
```json
{
  "error": {
    "code": "not_found",
    "message": "Model not found or does not belong to this user"
  }
}
```

---

### Endpoint: PUT /api/user/custom-models/{id} (capability override)

**Request (manual capability override):**
```json
{
  "capabilities": ["text", "vision"],
  "assigned_roles": ["text-gen", "vision"]
}
```

**Response (200):**
```json
{
  "id": 1,
  "name": "Qwen Max",
  "capabilities": ["text", "vision"],
  "assigned_roles": ["text-gen", "vision"],
  "status": "override",
  "last_tested_at": "2026-07-14T10:30:00Z",
  "last_error": null
}
```

## Technical Notes

- **Test image**: Use a hardcoded 10×10 solid cyan PNG (~100 bytes base64) embedded in the backend code. Do NOT fetch an external image — the test must be fully self-contained.
- **Timeouts**: Text generation: 30s. Vision: 60s. Embedding: 30s. These align with the existing `FIRECRAWL_TIMEOUT` convention.
- **Sequential execution**: Tests run sequentially within a single request to respect model API rate limits. Total maximum latency: ~120s for all three tests.
- **Decryption**: The stored encrypted API key is decrypted in-memory for the test request and never logged.
- **Logging**: All test requests and responses are logged at `DEBUG` level (not `INFO`) to avoid leaking API keys. Log fields: `model_id`, `test_type`, `status_code`, `latency_ms`.
- **Rate limiting**: Max 5 test requests per model per hour to prevent abuse of third-party APIs.
- **Embedding model detection**: The system tries `POST /embeddings` on the same `base_url` as the chat endpoint. If the embedding model differs from the chat model (common with DashScope), the user should configure the embedding model as a separate entry.
- **Dependency**: This capability depends on `multi-model-management` (the `user_custom_models` table and CRUD endpoints must exist first).
- **Frontend component**: Test results are displayed in a `TestResultPanel` sub-component within the `CustomModelsManager`. Each test type shows an icon (checkmark/X/dash), latency, and error detail.
