# Multi-Model Generation Page Integration

## Overview

Integrate user-configured custom models into the generation page model selection dropdowns. The system's five model roles (`large_llm`, `small_llm`, `vision_layout`, `audit_text`, `embedding`) each have distinct capability requirements. Custom models with matching capabilities appear alongside built-in provider models in the per-role dropdown selectors. The backend `GET /api/user/model-options` endpoint is extended to merge custom models into the role-based option lists, filtered by capability compatibility.

## Requirements

### Requirement 1: Custom models appear in model-option dropdowns

- **Description**: The `GET /api/user/model-options` response includes user-configured custom models in the appropriate role dropdowns, filtered by each model's detected capabilities and assigned roles.
- **Acceptance Criteria**:
  - `model_options_map_for_user()` in `core/provider_registry.py` is extended to merge custom models from `user_custom_models` into each role's options list
  - A custom model appears in a role's dropdown only if:
    - It has been assigned to that role via `assigned_roles`, OR
    - It has the required capabilities for the role (auto-matched):
      - `large_llm` requires `text` capability
      - `small_llm` requires `text` capability
      - `vision_layout` requires `text` AND `vision` capability
      - `audit_text` requires `text` capability
      - `embedding` requires `embedding` capability
  - Each custom model option includes a distinguishing `source: "custom"` field and the model's `id` from `user_custom_models`
  - Custom model options include the display format: `"{name} ({model_id})"` in the `label` field
  - Custom models are appended after built-in provider options (not interleaved) so built-in recommended models remain prominently visible
  - If a custom model has empty `capabilities` (never tested) and empty `assigned_roles`, it does NOT appear in any dropdown

### Requirement 2: Custom model option schema

- **Description**: Each custom model option in the dropdown uses an extended schema that the frontend can distinguish from built-in provider models.
- **Acceptance Criteria**:
  - Custom model options include all standard `ModelOption` fields (`model`, `label`, `recommended`) plus:
    - `source: "custom"` — distinguishes from provider-sourced options
    - `custom_model_id: number` — the `user_custom_models.id` for backend resolution
    - `provider_code: "custom"` — so the frontend can apply custom-specific styling
    - `provider_name: "自定义 / Custom"` — displayed as provider label
  - The `model` field contains the `default_model_id` from the custom model entry (the primary model identifier for API calls)
  - Existing built-in options are unchanged — no new fields added to non-custom options

### Requirement 3: Frontend dropdown integration

- **Description**: The generation page and settings page model dropdowns render custom model options with visual differentiation and proper selection behavior.
- **Acceptance Criteria**:
  - Custom model options render with a distinct visual indicator (e.g., a small "Custom" badge or different icon) next to the model name
  - When a user selects a custom model from a dropdown, the `model_choices` preference is saved via `PUT /api/user/preferences` with the custom model's `default_model_id` as the selection value
  - The current selection indicator correctly highlights a selected custom model
  - If the user's previously selected custom model is deleted, the dropdown shows a `selected_unavailable` warning (matching existing behavior for unavailable provider models) and falls back to the role's default
  - Model dropdowns remain functional when no custom models are configured (no regression)

### Requirement 4: Backend model resolution for custom models

- **Description**: When the generation engine processes a request and the user has selected a custom model for a role, the backend resolves and uses the custom model's endpoint (base_url + api_key) instead of the platform default.
- **Acceptance Criteria**:
  - The generation engine's model resolution logic checks if the selected model ID matches any custom model's `default_model_id`
  - If matched, the engine uses the custom model's `base_url`, `model_id` (the `default_model_id`), and decrypted `api_key` to construct the OpenAI-compatible client
  - If the custom model's API key is invalid or the endpoint is unreachable, the engine falls back to the platform default model for that role and emits a warning event via SSE
  - The SSE stream includes `custom_model_id` in route metadata when a custom model is used (already partially implemented — `event.custom_model_id` in `useGenerationSession.ts`)
  - Custom model resolution works for all five roles: `large_llm`, `small_llm`, `vision_layout`, `audit_text`, `embedding`
  - For vision requests, if a custom model is selected for `vision_layout`, the system sends the image content to the custom model's chat/completions endpoint (same OpenAI-compatible multimodal format)

### Requirement 5: Audit model fallback compatibility

- **Description**: The existing audit subsystem that reads from `user_custom_audit_models` continues to work during the migration period and gracefully defers to the new multi-model system.
- **Acceptance Criteria**:
  - The `ContentAuditor` (in `core/content_auditor.py`) first checks `user_custom_models` for models assigned to the `audit_text` role before falling back to the old `user_custom_audit_models` table
  - If both old and new tables have audit models configured, the new table takes precedence
  - The old `get_by_user_id()` function in `core/custom_audit.py` continues to work for backward compatibility
  - Migration script in the new `user_custom_models` module copies audit model data with `assigned_roles: ["audit_text"]` if capabilities include `text`

### Requirement 6: Quota and availability handling for custom models

- **Description**: Custom models integrate with the existing quota alert system so users can switch to/from custom models when quota limits are hit.
- **Acceptance Criteria**:
  - When a built-in provider returns a quota error during generation, the `switchQuotaModel` flow shows available custom models as alternatives (if they have matching capabilities)
  - Custom models are not subject to platform-level quota limits (they use the user's own API key)
  - The quota modal displays custom models with a "No quota limit" label to distinguish them from provider-limited models
  - If a custom model fails during quota-switch generation, the system emits a standard error event (no automatic retry to a different model)

## API Specification

### Extended response for GET /api/user/model-options (custom model entries)

The existing endpoint response is a `Record<string, ModelModuleConfig>`. Custom models are appended to each role's `options` array:

**Example response (single role):**
```json
{
  "large_llm": {
    "label": "Writing model",
    "description": "Main document generation model.",
    "options": [
      {
        "model": "qwen3.7-plus",
        "label": "Qwen3.7 Plus",
        "provider_code": "dashscope",
        "provider_name": "DashScope / Qwen",
        "recommended": true
      },
      {
        "model": "deepseek-chat",
        "label": "My DeepSeek (deepseek-chat)",
        "provider_code": "custom",
        "provider_name": "自定义 / Custom",
        "recommended": false,
        "source": "custom",
        "custom_model_id": 3
      }
    ],
    "source": "registry"
  }
}
```

### Resolution during generation (internal API flow)

No new public API endpoint is needed. The generation flow resolves custom models server-side:

```python
# Pseudocode for model resolution in the generation engine
def resolve_model_for_role(role: str, model_choice: str, user_id: int):
    # 1. Check custom models first
    custom_model = find_custom_model_by_choice(user_id, model_choice, role)
    if custom_model:
        return CustomModelClient(
            base_url=custom_model.base_url,
            model_id=custom_model.default_model_id,
            api_key=decrypt_api_key(custom_model.encrypted_api_key),
        )
    # 2. Fall back to provider registry
    return ProviderRegistry.resolve(role, model_choice)
```

## Technical Notes

- **Merge order**: Custom models appear AFTER built-in options in each role's dropdown to preserve the recommended/default model visibility. Within the custom section, models are sorted alphabetically by name.
- **Capability filtering**: The `model_options_map_for_user()` function calls `get_models_for_user(user_id)` and filters by role-capability mapping before appending to options.
- **Deduplication**: If a custom model is assigned to multiple roles, it appears in each relevant role's dropdown. The same `custom_model_id` may appear across multiple roles.
- **Selection persistence**: Custom model selections are stored in `user_preferences.model_choices` using the `default_model_id` string (same format as provider models). The backend differentiates by checking `user_custom_models` table when resolving.
- **Visual styling**: Frontend applies a `bg-night-900/50 border-signal-cyan/20` style to custom model options with a small `⚙` icon prefix. This aligns with the existing cyberpunk design system.
- **No new frontend components in the generation page**: The integration modifies the existing `ModelModuleConfig` / `ModelOption` rendering pipeline — no new page-level components are created. The dropdown component already handles `provider_code` differentiation; this spec adds `"custom"` as a new provider code value.
- **Dependency chain**: This spec depends on both `multi-model-management` (for the data model and CRUD APIs) and `model-capability-testing` (for reliable capability detection). Without capability testing, auto-matching cannot populate dropdowns correctly.
- **SSE route metadata**: The generation SSE stream already includes `custom_model_id` field in route events. This field is populated when a custom model is used, enabling the frontend `RunOverview` component to display which custom model processed the generation.
- **Embedding integration**: When a custom model is assigned to the `embedding` role, it is used for vector store operations (ChromaDB ingestion and retrieval). The embedding model uses a different API pattern (`POST /embeddings` instead of `POST /chat/completions`). The `ContentGenerator` must branch on the role to use the correct endpoint format.
- **Performance**: Custom model resolution adds one additional database query per generation request (lookup `user_custom_models` by user_id + role match). This is cached per session to avoid repeated lookups.
