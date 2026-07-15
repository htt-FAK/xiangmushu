# Custom Models API Reference

> **Base path**: `/api/user/custom-models`
> **Auth**: Bearer JWT (all endpoints)
> **Content-Type**: `application/json` (where applicable)

---

## Overview

The multi-custom-model management API lets authenticated users configure, test, and assign multiple OpenAI-compatible AI models. Each model has its own base URL, model IDs, API key, detected capabilities, and role assignments.

**Limits**:

- 20 custom models per user
- 10 model creations per user per hour
- 5 capability tests per model per hour

---

## Authentication

All endpoints require a valid JWT in the `Authorization` header:

```
Authorization: Bearer <jwt>
```

Obtain a token via `POST /api/auth/login`. Tokens expire per the `AUTH_JWT_EXPIRY` configuration. Requests without a valid token receive `401 Unauthorized`.

---

## Endpoints

### 1. List Models

```
GET /api/user/custom-models
```

Returns all custom models for the authenticated user, ordered by `created_at` descending (newest first).

**Request**: No body required.

**Response (200)**:

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

**Response (no models, 200)**:

```json
{
  "models": []
}
```

> [!NOTE]
> The API key is never returned in plaintext. Only a masked preview is included (format: first 4 chars + `...` + last 2 chars).

**Example**:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/user/custom-models
```

---

### 2. Create Model

```
POST /api/user/custom-models
```

Adds a new custom model. The system performs a live probe before saving. If the probe fails, the model is not created.

**Request**:

```json
{
  "name": "DeepSeek Chat",
  "base_url": "https://api.deepseek.com/v1",
  "model_id": "deepseek-chat,deepseek-coder",
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
  "default_model_id": "deepseek-chat"
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `name` | string | Yes | User-friendly label (non-empty) |
| `base_url` | string | Yes | OpenAI-compatible API base URL. Must pass SSRF validation (no private/loopback/link-local IPs) |
| `model_id` | string | Yes | Comma-separated model identifiers (non-empty) |
| `api_key` | string | Yes | API key (min 8 characters). Encrypted at rest via Fernet |
| `default_model_id` | string | No | Primary model ID. Defaults to the first value in `model_id` |

**Response (201)**:

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

**Response (422, validation error)**:

```json
{
  "error": {
    "code": "ssrf_rejected",
    "message": "base_url host resolved to a disallowed address"
  }
}
```

**Rate limit**: 10 creations per user per hour. Returns `429 Too Many Requests` with `Retry-After` header when exceeded.

**Example**:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DeepSeek Chat",
    "base_url": "https://api.deepseek.com/v1",
    "model_id": "deepseek-chat",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
  }' \
  https://api.example.com/api/user/custom-models
```

---

### 3. Update Model

```
PUT /api/user/custom-models/{id}
```

Partial update. Only provided fields are modified. If `base_url`, `model_id`, or `api_key` changes, a new probe is triggered before saving. Changes to `name` or `assigned_roles` alone skip the probe.

**Request**:

```json
{
  "name": "New Model Name",
  "assigned_roles": ["text-gen", "vision"]
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `name` | string | No | Updated display name |
| `base_url` | string | No | New base URL (triggers re-probe) |
| `model_id` | string | No | New model IDs (triggers re-probe) |
| `api_key` | string | No | New API key (triggers re-probe) |
| `default_model_id` | string | No | New primary model ID |
| `assigned_roles` | string[] | No | Array of roles: `text-gen`, `vision`, `embedding`, `audit`, `small-llm` |
| `capabilities` | string[] | No | Manual capability override: `text`, `vision`, `embedding`. Sets `status` to `"override"` |

**Response (200)**: Updated model object (same schema as GET response).

**Response (404)**:

```json
{
  "error": {
    "code": "not_found",
    "message": "Model not found or does not belong to this user"
  }
}
```

**Example**:

```bash
curl -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assigned_roles": ["text-gen", "audit"]}' \
  https://api.example.com/api/user/custom-models/2
```

---

### 4. Delete Model

```
DELETE /api/user/custom-models/{id}
```

Removes the model and its encrypted API key from the database.

**Request**: No body required.

**Response (204)**: No content.

**Response (404)**:

```json
{
  "error": {
    "code": "not_found",
    "message": "Model not found or does not belong to this user"
  }
}
```

> [!NOTE]
> An `API_KEY_DELETED` audit log entry is recorded with the model ID. The frontend handles confirmation dialogs; there is no secondary confirmation endpoint.

**Example**:

```bash
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/user/custom-models/2
```

---

### 5. Test Capabilities

```
POST /api/user/custom-models/{id}/test
```

Runs capability probes against the model. Tests execute sequentially (not in parallel) to respect upstream rate limits.

**Request**:

```json
{
  "test_types": ["text", "vision", "embedding"]
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `test_types` | string[] | No | Subset of `["text", "vision", "embedding"]`. Defaults to all three if omitted or empty |

**Response (200, all passed)**:

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

**Response (200, partial failure)**:

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

**Response (422, auth failure)**:

```json
{
  "error": {
    "code": "auth",
    "message": "API key is invalid or expired. Please update the model configuration."
  }
}
```

> [!WARNING]
> If the API key is invalid (probe returns auth error), the entire test is rejected with 422. No partial results are saved.

**Response (404)**:

```json
{
  "error": {
    "code": "not_found",
    "message": "Model not found or does not belong to this user"
  }
}
```

**Rate limit**: 5 tests per model per hour. Returns `429` when exceeded.

**Timeouts**: Text: 30s. Vision: 60s. Embedding: 30s. Maximum total latency: ~120s for all three tests.

**Example**:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test_types": ["text", "vision"]}' \
  https://api.example.com/api/user/custom-models/1/test
```

---

### 6. Assign Roles

```
POST /api/user/custom-models/{id}/assign
```

Assigns one or more system roles to a model. Multiple models can share the same role.

**Request**:

```json
{
  "assigned_roles": ["text-gen", "vision"],
  "default_model_id": "deepseek-chat"
}
```

| Field | Type | Required | Description |
|:------|:-----|:---------|:------------|
| `assigned_roles` | string[] | Yes | Roles to assign. Allowed values: `text-gen`, `vision`, `embedding`, `audit`, `small-llm` |
| `default_model_id` | string | No | Override the primary model ID for this entry |

**Response (200)**:

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

> [!NOTE]
> A role can be assigned without the corresponding capability being tested. In this case, the response includes a `warnings` array explaining which roles were assigned without capability verification.

**Response (404)**:

```json
{
  "error": {
    "code": "not_found",
    "message": "Model not found or does not belong to this user"
  }
}
```

**Example**:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assigned_roles": ["text-gen", "audit"]}' \
  https://api.example.com/api/user/custom-models/2/assign
```

---

## Error Codes

| Code | HTTP Status | Description (en) | 描述 (zh) |
|:-----|:------------|:-----------------|:----------|
| `url_format` | 422 | Invalid URL format in `base_url` | `base_url` 格式无效 |
| `ssrf_rejected` | 422 | `base_url` resolved to a private/loopback/link-local address | `base_url` 解析到内网/回环/链路本地地址 |
| `auth` | 422 | API key is invalid or expired | API key 无效或已过期 |
| `network` | 422 | Network error during probe (connection refused, DNS failure) | 探测时网络错误（连接拒绝、DNS 失败） |
| `timeout` | 422 | Probe request timed out | 探测请求超时 |
| `model_not_found` | 422 | Specified `default_model_id` not found on the remote endpoint | 远程端点未找到指定的 `default_model_id` |
| `bad_response` | 422 | Model returned a malformed or unexpected response | 模型返回格式异常或意外响应 |
| `not_found` | 404 | Model does not exist or does not belong to this user | 模型不存在或不属于当前用户 |
| `invalid_role` | 422 | Role value not in allowed set (`text-gen`, `vision`, `embedding`, `audit`, `small-llm`) | 角色值不在允许范围内 |
| `limit_exceeded` | 422 | User has reached the maximum of 20 custom models | 用户已达到 20 个自定义模型上限 |
| `api_key_length` | 422 | API key is shorter than 8 characters | API key 长度不足 8 位 |
| `rate_limited` | 429 | Rate limit exceeded (10 creations/hr or 5 tests/model/hr) | 请求频率超限（每小时 10 次创建或每模型 5 次测试） |

---

## Rate Limits Summary

| Operation | Limit | Window | Response on Excess |
|:----------|:------|:-------|:-------------------|
| Model creation (`POST /custom-models`) | 10 | Per user, per hour | `429` + `Retry-After` header |
| Capability test (`POST /custom-models/{id}/test`) | 5 | Per model, per hour | `429` + `Retry-After` header |
| Max models per user | 20 | Lifetime | `422` (`limit_exceeded`) |

---

## Extended Endpoint: Model Options

The existing `GET /api/user/model-options` endpoint is extended to include custom models in each role's dropdown. Custom model options include:

```json
{
  "model": "deepseek-chat",
  "label": "My DeepSeek (deepseek-chat)",
  "provider_code": "custom",
  "provider_name": "自定义 / Custom",
  "recommended": false,
  "source": "custom",
  "custom_model_id": 3
}
```

Custom models appear after built-in provider options. A model appears in a role's dropdown if it has been assigned to that role or auto-matched by capability:

| System Role | Required Capability |
|:------------|:--------------------|
| `large_llm` | `text` |
| `small_llm` | `text` |
| `vision_layout` | `text` AND `vision` |
| `audit_text` | `text` |
| `embedding` | `embedding` |
