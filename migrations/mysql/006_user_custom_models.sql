-- 006_user_custom_models.sql
--
-- Multi-model management support
-- This migration creates the user_custom_models table which replaces the
-- single-model user_custom_audit_models table. Each user can now configure
-- multiple custom OpenAI-compatible models with different capabilities.
--
-- Key differences from user_custom_audit_models:
-- - No UNIQUE constraint on user_id (multiple models per user)
-- - Added capabilities_json (JSON array of detected capabilities)
-- - Added assigned_roles_json (JSON array of assigned roles)
-- - Added default_model_id (primary model ID for this entry)
-- - Added last_error field for error tracking

-- Step 1: Create the new multi-model table
CREATE TABLE IF NOT EXISTS user_custom_models (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    name VARCHAR(64) NOT NULL,
    base_url VARCHAR(512) NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    api_key_hint VARCHAR(32) NULL,
    capabilities_json JSON NULL,
    assigned_roles_json JSON NULL,
    default_model_id VARCHAR(128) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'untested',
    last_tested_at TIMESTAMP NULL,
    last_error TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_custom_models_user (user_id),
    INDEX idx_user_custom_models_status (status),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Step 2: Migrate data from user_custom_audit_models (if exists)
-- This is a one-time migration that copies existing audit models into the new table
-- as a special case where all models are assigned to 'audit' role
INSERT INTO user_custom_models (user_id, name, base_url, model_id, encrypted_api_key, api_key_hint, default_model_id, status, last_tested_at, last_error, created_at, updated_at)
SELECT 
    user_id,
    name,
    base_url,
    model_id,
    encrypted_api_key,
    api_key_hint,
    model_id,  -- Use model_id as default_model_id
    status,
    validated_at,
    NULL,  -- No error history for migrated models
    created_at,
    updated_at
FROM user_custom_audit_models
ON DUPLICATE KEY UPDATE
    -- This should not happen (user_id is not unique in new table), but include for safety
    name = VALUES(name);

-- Step 3: Add audit role assignment to migrated models
-- Update the assigned_roles_json for all migrated models to indicate they are audit models
UPDATE user_custom_models 
SET assigned_roles_json = JSON_ARRAY('audit')
WHERE assigned_roles_json IS NULL;

-- Step 4: Add capabilities_json based on the model's known capabilities
-- For now, assume all migrated models support text (safe assumption)
UPDATE user_custom_models 
SET capabilities_json = JSON_ARRAY('text')
WHERE capabilities_json IS NULL;

-- Step 5: Mark the old table as deprecated (comment only, no schema change)
-- The old user_custom_audit_models table is now deprecated but kept for backward compatibility
-- It will be removed in a future major version after this feature is stable
