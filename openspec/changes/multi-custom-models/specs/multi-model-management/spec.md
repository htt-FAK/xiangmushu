# Multi-Model Management

## Overview

Upgrade the existing single-model custom audit configuration (one model per user) to a full multi-model management system. Users can add, edit, delete, and list multiple custom OpenAI-compatible models, each independently configured with its own name, base URL, model IDs, API key, capabilities, and role assignments. The system replaces the current `user_custom_audit_models` table and `CustomAuditModelCard` component with a richer data model and management UI.

## Requirements

### Requirement 1: Multi-model data model

- **Description**: Replace the current single-model-per-user constraint with a new `user_custom_models` table that allows multiple models per user. Each model entry stores name, base URL, model ID(s), encrypted API key, detected capabilities, assigned roles, status, and timestamps.
- **Acceptance Criteria**:
  - New table `user_custom_models` is created with columns: `id`, `user_id`, `name`, `base_url`, `model_id` (supports comma-separated multiple IDs), `encrypted_api_key`, `capabilities` (JSON array), `assigned_roles` (JSON array), `default_model_id`, `status`, `last_tested_at`, `last_error`, `created_at`, `updated_at`
  - `user_id` no longer has a UNIQUE constraint — multiple rows per user are allowed
  - Existing data from `user_custom_audit_models` is migrated to `user_custom_models` with `status='validated'` preserved
  - Old `user_custom_audit_models` table remains but is marked as deprecated
  - API keys continue to be encrypted at rest using the existing Fernet encryption (`core.billing.encrypt_api_key`)

### Requirement 2: List all models (GET)

- **Description**: Authenticated users can retrieve a list of all their configured custom models.
- **Acceptance Criteria**:
  - `GET /api/user/custom-models` returns a JSON object with `models` array
  - Each model in the array includes: `id`, `name`, `base_url`, `model_id`, `default_model_id`, `capabilities`, `assigned_roles`, `status`, `last_tested_at`, `last_error`, `created_at`, `updated_at`, `api_key_preview`
  - API key is never returned in plaintext — only a masked preview (e.g., `sk-a1...ef`)
  - Empty list `{"models": []}` is returned when no models are configured (not 404)
  - Results are ordered by `created_at` descending (newest first)
  - Only authenticated users can access their own models (enforced by `get_current_user` dependency)

### Requirement 3: Create model (POST)

- **Description**: Users can add a new custom model with name, base URL, model ID(s), and API key.
- **Acceptance Criteria**:
  - `POST /api/user/custom-models` accepts `name`, `base_url`, `model_id`, `api_key`, and optional `default_model_id`
  - All required fields are validated: non-empty name, valid URL format for `base_url`, non-empty `model_id`, non-empty `api_key`
  - URL is validated against SSRF attacks (same `validate_base_url` logic as current implementation — no private/loopback/link-local IPs)
  - A live probe is performed via `probe_custom_model` before saving; on probe failure, 422 is returned with structured error `{code, message}`
  - On successful probe, model is saved with `status='validated'`
  - If `model_id` contains comma-separated values and `default_model_id` is not provided, the first model ID becomes the default
  - Returns the created model object with all fields
  - Rate limiting: max 10 model creations per user per hour

### Requirement 4: Update model (PUT)

- **Description**: Users can update an existing model's configuration (name, base URL, model IDs, API key, assigned roles, default model ID).
- **Acceptance Criteria**:
  - `PUT /api/user/custom-models/{id}` accepts partial updates — only provided fields are updated
  - If `base_url`, `model_id`, or `api_key` changes, a new probe is triggered before saving
  - If only `name` or `assigned_roles` changes, no probe is required
  - `assigned_roles` accepts an array of strings; each role must be one of: `text-gen`, `vision`, `embedding`, `audit`, `small-llm`
  - Returns the updated model object
  - Returns 404 if the model does not exist or does not belong to the current user
  - `updated_at` timestamp is automatically refreshed on every update

### Requirement 5: Delete model (DELETE)

- **Description**: Users can delete an individual custom model by ID.
- **Acceptance Criteria**:
  - `DELETE /api/user/custom-models/{id}` removes the model and its encrypted API key from the database
  - Returns `204 No Content` on success
  - Returns 404 if the model does not exist or does not belong to the current user
  - Deletion is confirmed without a secondary confirmation endpoint (frontend handles confirmation dialog)
  - Audit log entry is recorded (`API_KEY_DELETED` event with model ID)

### Requirement 6: Role assignment

- **Description**: Users can assign one or more system roles to a model, determining where the model can be used (text generation, vision, embedding, audit, small LLM tasks).
- **Acceptance Criteria**:
  - `POST /api/user/custom-models/{id}/assign` accepts `assigned_roles` (array) and optional `default_model_id`
  - Supported roles: `text-gen`, `vision`, `embedding`, `audit`, `small-llm`
  - A role can only be assigned if the model has the corresponding capability (e.g., `vision` role requires `vision` capability); if capabilities haven't been tested yet, assignment is allowed with a warning flag in the response
  - Multiple models can be assigned to the same role — the system uses the `default_model_id` or first available model for that role
  - Returns the updated model with new assignments
  - When no model is assigned to a required role, the system falls back to the platform default model (existing behavior)

### Requirement 7: Frontend model management UI

- **Description**: A new `CustomModelsManager` component replaces the existing `CustomAuditModelCard`, providing a complete CRUD interface for managing multiple models.
- **Acceptance Criteria**:
  - `CustomModelsManager` is integrated into `SettingsPage` replacing the old `CustomAuditModelCard`
  - Model list displays all configured models as cards, sorted by status (tested first) then by name
  - Each `ModelCard` shows: model name, base URL (truncated), model ID(s), capability badges (green for supported, gray for untested/unsupported), role badges, status indicator, and action buttons (Test, Edit, Delete)
  - `AddModelDialog` provides form fields for: name, base URL, model ID (with hint for comma-separated values), API key (password input), and default model ID (dropdown populated from parsed model IDs)
  - Form validation: required fields highlighted, URL format validated client-side, API key minimum length (8 characters)
  - Delete action shows a confirmation dialog before proceeding
  - Empty state displays an illustrative message with an "Add your first model" CTA button
  - Loading states: skeleton placeholders during initial fetch, spinner on save/delete buttons during operations
  - Error handling: inline error banners with localized messages (using existing `i18n` system)

## API Specification

### Endpoint: GET /api/user/custom-models

**Headers**: `Authorization: Bearer <jwt>`

**Response (200):**
```json
{
  "models": [
    {
      "id": 1,
      "name": "Qwen Max",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "model_id": "qwen-max,qwen-plus",
      "default_model_id": "qwen-max",
      "capabilities": ["text", "embedding"],
      "assigned_roles": ["text-gen", "embedding"],
      "status": "tested",
      "last_tested_at": "2026-07-14T10:30:00Z",
      "last_error": null,
      "api_key_preview": "sk-a1...ef",
      "created_at": "2026-07-10T08:00:00Z",
      "updated_at": "2026-07-14T10:30:00Z"
    }
  ]
}
```

**Response (no models, 200):**
```json
{
  "models": []
}
```

---

### Endpoint: POST /api/user/custom-models

**Headers**: `Authorization: Bearer <jwt>`, `Content-Type: application/json`

**Request:**
```json
{
  "name": "DeepSeek Chat",
  "base_url": "https://api.deepseek.com/v1",
  "model_id": "deepseek-chat,deepseek-coder",
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
  "default_model_id": "deepseek-chat"
}
```

**Response (201):**
```json
{
  "id": 2,
  "name": "DeepSeek Chat",
  "base_url": "https://api.deepseek.com/v1",
  "model_id": "deepseek-chat,deepseek-coder",
  "default_model_id": "deepseek-chat",
  "capabilities": [],
  "assigned_roles": [],
  "status": "validated",
  "last_tested_at": "2026-07-14T12:00:00Z",
  "last_error": null,
  "api_key_preview": "sk-xx...xx",
  "created_at": "2026-07-14T12:00:00Z",
  "updated_at": "2026-07-14T12:00:00Z"
}
```

**Response (422, validation error):**
```json
{
  "error": {
    "code": "ssrf_rejected",
    "message": "base_url host resolved to a disallowed address"
  }
}
```

---

### Endpoint: PUT /api/user/custom-models/{id}

**Headers**: `Authorization: Bearer <jwt>`, `Content-Type: application/json`

**Request (partial update):**
```json
{
  "name": "New Model Name",
  "assigned_roles": ["text-gen", "vision"]
}
```

**Response (200):** Updated model object (same schema as GET response)

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

### Endpoint: DELETE /api/user/custom-models/{id}

**Headers**: `Authorization: Bearer <jwt>`

**Response (204):** No content

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

### Endpoint: POST /api/user/custom-models/{id}/assign

**Headers**: `Authorization: Bearer <jwt>`, `Content-Type: application/json`

**Request:**
```json
{
  "assigned_roles": ["text-gen", "vision"],
  "default_model_id": "deepseek-chat"
}
```

**Response (200):**
```json
{
  "id": 2,
  "name": "DeepSeek Chat",
  "assigned_roles": ["text-gen", "vision"],
  "default_model_id": "deepseek-chat",
  "capabilities": ["text"],
  "warnings": ["vision role assigned but model has not been tested for vision capability"]
}
```

## Technical Notes

- **Backward compatibility**: The old endpoints (`GET/POST/DELETE /api/user/custom-audit-model`) remain functional and delegate to the new table. Old `CustomAuditModelCard` component is deprecated in favor of `CustomModelsManager`.
- **Migration**: Automated migration runs on first startup — existing `user_custom_audit_models` data is copied to `user_custom_models` with `status='validated'` and empty `capabilities`/`assigned_roles` arrays.
- **Encryption**: API keys use the same Fernet encryption as existing system (`core.billing.encrypt_api_key` / `decrypt_api_key`).
- **SSRF protection**: All URL validation reuses the existing `validate_base_url` function from `core/custom_audit.py` — blocks private IPs, loopback, link-local addresses.
- **Component architecture**: The new `CustomModelsManager` component tree includes `ModelList` → `ModelCard` (with `CapabilityBadges`, `RoleBadges`, action buttons) + `AddModelDialog` + `TestResultPanel`.
- **i18n**: All new UI strings must be added to both `zh` and `en` dictionaries in `src/i18n.ts` under the `settings.customModels.*` namespace.
- **Max model limit**: Each user can configure a maximum of 20 custom models to prevent abuse.
