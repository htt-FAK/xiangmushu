-- 005_user_custom_audit_models.sql
--
-- Per-user custom audit model configuration. Lets a user plug in their own
-- OpenAI-compatible model (base_url + model_id + api_key) to handle the
-- post-generation content-audit pass that is otherwise served by the
-- platform-default AUDIT_TEXT_MODEL.
--
-- One record per user (user_id UNIQUE). The encrypted api_key reuses the
-- same Fernet primitive used by provider_credentials so that key rotation,
-- preview (key_hint), and at-rest protection remain consistent.

CREATE TABLE IF NOT EXISTS user_custom_audit_models (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    name VARCHAR(64) NOT NULL,
    base_url VARCHAR(512) NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    api_key_hint VARCHAR(32) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'untested',
    validated_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_custom_audit_models_user (user_id),
    KEY idx_user_custom_audit_models_status (status),
    CONSTRAINT fk_user_custom_audit_models_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
