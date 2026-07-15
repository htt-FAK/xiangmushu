# Migration Guide v2: Single-Model to Multi-Model

> **Target version**: v2.0.0 | **Migration file**: `migrations/mysql/006_user_custom_models.sql`

---

## Background

Prior to v2.0.0, the system supported only a single custom audit model per user via the `user_custom_audit_models` table. This limitation prevented users from configuring separate models for text generation, vision, and embedding tasks.

The multi-model system replaces this with a `user_custom_models` table that allows multiple models per user, each with independent capabilities, role assignments, and API keys.

---

## What's New

| Component | Description |
|:----------|:------------|
| **`user_custom_models` table** | New table supporting multiple models per user with `capabilities_json`, `assigned_roles_json`, `default_model_id`, `last_error`, and `status` fields |
| **6 new API endpoints** | `GET/POST/PUT/DELETE /api/user/custom-models`, `POST .../test`, `POST .../assign` |
| **Frontend components** | `CustomModelsManager`, `ModelList`, `ModelCard`, `AddModelDialog`, `TestResultPanel`, `TestModelButton` replace the deprecated `CustomAuditModelCard` |
| **Capability testing** | Automatic detection of text, vision, and embedding capabilities via live probes |
| **Role assignment** | Five roles: `text-gen`, `vision`, `embedding`, `audit`, `small-llm` |

---

## Automatic Migration

The migration runs automatically on the next server startup when `MYSQL_AUTO_MIGRATE=1` (default).

### What happens

1. **Table creation**: `user_custom_models` is created with the new schema (see `006_user_custom_models.sql`)
2. **Data copy**: All rows from `user_custom_audit_models` are copied into `user_custom_models`:

   | Old Field | New Field | Notes |
   |:----------|:----------|:------|
   | `user_id` | `user_id` | Direct copy |
   | `name` | `name` | Direct copy |
   | `base_url` | `base_url` | Direct copy |
   | `model_id` | `model_id` | Direct copy |
   | `encrypted_api_key` | `encrypted_api_key` | Direct copy (Fernet-encrypted) |
   | `api_key_hint` | `api_key_hint` | Direct copy |
   | `model_id` | `default_model_id` | Model ID reused as default |
   | `status` | `status` | Preserved (typically `validated`) |
   | `validated_at` | `last_tested_at` | Timestamp preserved |
   | `created_at` | `created_at` | Direct copy |
   | `updated_at` | `updated_at` | Direct copy |

3. **Default assignments**: Migrated models get:
   - `assigned_roles_json = ["audit"]` (since they were audit models)
   - `capabilities_json = ["text"]` (safe assumption for migrated models)
   - `last_error = NULL`

4. **Old table preserved**: `user_custom_audit_models` is NOT dropped. It remains functional for backward compatibility but is marked as deprecated.

---

## Verifying Migration

After the migration runs, verify your data with these SQL queries:

### 1. Check row counts match

```sql
SELECT
  (SELECT COUNT(*) FROM user_custom_audit_models) AS old_count,
  (SELECT COUNT(*) FROM user_custom_models) AS new_count;
```

Both counts should be equal (or new_count may be higher if users added models via the new API).

### 2. Verify migrated models have audit role

```sql
SELECT COUNT(*) AS audit_models
FROM user_custom_models
WHERE JSON_CONTAINS(assigned_roles_json, '"audit"');
```

This should match the old table's row count.

### 3. Verify API keys are intact

```sql
SELECT id, name, LENGTH(encrypted_api_key) AS key_len, api_key_hint
FROM user_custom_models
WHERE encrypted_api_key IS NOT NULL
  AND encrypted_api_key != '';
```

All migrated rows should have non-empty encrypted keys.

### 4. Check status preserved

```sql
SELECT status, COUNT(*) AS cnt
FROM user_custom_models
GROUP BY status;
```

Migrated models should show `status = 'validated'`.

### 5. Test the new API

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/api/user/custom-models
```

The response should include your migrated model(s) with `assigned_roles: ["audit"]`.

---

## Old Endpoint Deprecation

The following endpoints remain functional but are deprecated:

| Endpoint | Status | Removal Target |
|:---------|:-------|:---------------|
| `GET /api/user/custom-audit-model` | Deprecated | v2.1.0 |
| `POST /api/user/custom-audit-model` | Deprecated | v2.1.0 |
| `DELETE /api/user/custom-audit-model` | Deprecated | v2.1.0 |

**What to do**: Update your API clients to use the new `/api/user/custom-models` endpoints. The old endpoints delegate to the new table internally, so data is consistent, but they will be removed in v2.1.0.

**Migration mapping**:

| Old Endpoint | New Equivalent |
|:-------------|:---------------|
| `GET /api/user/custom-audit-model` | `GET /api/user/custom-models` (returns array; pick the one you need) |
| `POST /api/user/custom-audit-model` | `POST /api/user/custom-models` (same fields) |
| `DELETE /api/user/custom-audit-model` | `DELETE /api/user/custom-models/{id}` (requires model ID) |

---

## Rollback Plan

If the migration causes issues, follow these steps to revert:

### 1. Stop the server

```bash
# Gracefully stop the FastAPI server
kill -SIGTERM <pid>
```

### 2. Drop the new table

```sql
DROP TABLE IF EXISTS user_custom_models;
```

### 3. Revert the migration

Delete the migration record (if your migration framework tracks applied migrations):

```sql
DELETE FROM _migrations WHERE name = '006_user_custom_models';
```

Or, if using auto-migrate, simply remove the `006_user_custom_models.sql` file from the `migrations/mysql/` directory.

### 4. Restart the server

The old `user_custom_audit_models` table is untouched and will continue to work.

> [!WARNING]
> Any models created via the new API endpoints after migration will be lost on rollback. Export them first if needed:
> ```bash
> curl -H "Authorization: Bearer $TOKEN" \
>   https://api.example.com/api/user/custom-models > custom-models-backup.json
> ```

---

## FAQ

### Will my existing audit model still work?

**中文**：会。迁移后，你的旧审核模型会自动复制到新表，分配 `audit` 角色，状态保持 `validated`。旧端点也继续可用。

**English**: Yes. Your old audit model is automatically copied to the new table with the `audit` role assigned and `validated` status preserved. The old endpoints also remain functional.

### Do I need to change anything?

**中文**：不需要立即操作。迁移是自动的，旧端点继续工作。但建议在 v2.1.0 之前迁移到新 API，因为旧端点将被移除。

**English**: No immediate action required. The migration is automatic, and old endpoints continue to work. However, we recommend migrating to the new API before v2.1.0, when old endpoints will be removed.

### What if I want both old and new tables temporarily?

**中文**：迁移后两张表同时存在。旧表数据不变，新表包含迁移数据和任何新增模型。你可以同时使用两套端点，数据是一致的。

**English**: Both tables coexist after migration. The old table data is unchanged, and the new table contains migrated data plus any new models. You can use both sets of endpoints simultaneously; data is consistent.

### Can I re-run the migration if something went wrong?

**中文**：可以。迁移使用 `CREATE TABLE IF NOT EXISTS` 和 `INSERT ... ON DUPLICATE KEY UPDATE`，重复运行是安全的。但建议在重新运行前先检查问题原因。

**English**: Yes. The migration uses `CREATE TABLE IF NOT EXISTS` and `INSERT ... ON DUPLICATE KEY UPDATE`, making it safe to re-run. But check the root cause first.

### What happens to the old `CustomAuditModelCard` component?

**中文**：前端旧组件 `CustomAuditModelCard` 已被 `CustomModelsManager` 替代。旧组件文件保留但不再渲染，标记为 deprecated。

**English**: The old `CustomAuditModelCard` component is replaced by `CustomModelsManager`. The old file is retained but no longer rendered, marked as deprecated.

---

## Related Documentation

- [API Reference](api-custom-models.md)
- [Multi-Model Feature Guide](features/multi-model.md)
- [Migration SQL](../migrations/mysql/006_user_custom_models.sql)
