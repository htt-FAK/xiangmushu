CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NULL,
    display_name VARCHAR(255) NULL,
    preferred_language VARCHAR(32) NOT NULL DEFAULT 'zh',
    model_choices_json JSON NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    is_verified TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS roles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description VARCHAR(512) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_roles_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS email_verification_codes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NULL,
    purpose VARCHAR(64) NOT NULL DEFAULT 'login',
    expires_at TIMESTAMP NOT NULL,
    consumed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_email_codes_email_purpose (email, purpose),
    KEY idx_email_codes_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id BIGINT PRIMARY KEY,
    preferred_language VARCHAR(32) NOT NULL DEFAULT 'zh',
    model_choices_json JSON NULL,
    settings_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_preferences_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS model_providers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    provider_type VARCHAR(64) NOT NULL DEFAULT 'openai_compatible',
    base_url VARCHAR(512) NULL,
    auth_mode VARCHAR(64) NOT NULL DEFAULT 'api_key',
    supports_openai_compat TINYINT(1) NOT NULL DEFAULT 1,
    supports_streaming TINYINT(1) NOT NULL DEFAULT 1,
    supports_search TINYINT(1) NOT NULL DEFAULT 0,
    supports_vision TINYINT(1) NOT NULL DEFAULT 0,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    config_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_model_providers_code (code),
    KEY idx_model_providers_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS model_catalog (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    provider_id BIGINT NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    role_key VARCHAR(64) NOT NULL,
    capabilities_json JSON NULL,
    input_price_per_1k DECIMAL(12, 8) NULL,
    output_price_per_1k DECIMAL(12, 8) NULL,
    context_window INT NULL,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    config_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_model_catalog_provider_model_role (provider_id, model_id, role_key),
    KEY idx_model_catalog_role_enabled (role_key, enabled),
    CONSTRAINT fk_model_catalog_provider FOREIGN KEY (provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS provider_credentials (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    owner_user_id BIGINT NULL,
    provider_id BIGINT NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    key_hint VARCHAR(32) NULL,
    scopes_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'untested',
    validation_json JSON NULL,
    validated_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_provider_credentials_owner_provider (owner_user_id, provider_id),
    KEY idx_provider_credentials_provider_status (provider_id, status),
    CONSTRAINT fk_provider_credentials_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_provider_credentials_provider FOREIGN KEY (provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_model_choices (
    user_id BIGINT NOT NULL,
    module_key VARCHAR(64) NOT NULL,
    provider_id BIGINT NULL,
    model_catalog_id BIGINT NULL,
    provider_code VARCHAR(64) NULL,
    model_id VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, module_key),
    KEY idx_user_model_choices_model (model_id),
    CONSTRAINT fk_user_model_choices_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_model_choices_provider FOREIGN KEY (provider_id) REFERENCES model_providers(id) ON DELETE SET NULL,
    CONSTRAINT fk_user_model_choices_catalog FOREIGN KEY (model_catalog_id) REFERENCES model_catalog(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS generation_sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_key VARCHAR(128) NOT NULL,
    owner_user_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    progress_percent DECIMAL(5, 2) NOT NULL DEFAULT 0,
    current_task VARCHAR(512) NULL,
    params_json JSON NULL,
    result_json JSON NULL,
    error_summary TEXT NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost_cny DECIMAL(14, 8) NOT NULL DEFAULT 0,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_generation_sessions_key (session_key),
    KEY idx_generation_sessions_owner_status (owner_user_id, status),
    KEY idx_generation_sessions_created_at (created_at),
    CONSTRAINT fk_generation_sessions_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS generated_articles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    owner_user_id BIGINT NOT NULL,
    generation_session_id BIGINT NULL,
    title VARCHAR(512) NOT NULL,
    summary TEXT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'done',
    template_name VARCHAR(255) NULL,
    knowledge_base_slug VARCHAR(128) NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost_cny DECIMAL(14, 8) NOT NULL DEFAULT 0,
    model_usage_json JSON NULL,
    metadata_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    KEY idx_generated_articles_owner_created (owner_user_id, created_at),
    KEY idx_generated_articles_session (generation_session_id),
    FULLTEXT KEY ft_generated_articles_title_summary (title, summary),
    CONSTRAINT fk_generated_articles_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_generated_articles_session FOREIGN KEY (generation_session_id) REFERENCES generation_sessions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS artifact_objects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    artifact_uuid CHAR(36) NOT NULL,
    owner_user_id BIGINT NOT NULL,
    generation_session_id BIGINT NULL,
    generated_article_id BIGINT NULL,
    knowledge_source_id BIGINT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    storage_backend VARCHAR(64) NOT NULL DEFAULT 'local',
    bucket_name VARCHAR(255) NULL,
    object_key VARCHAR(1024) NOT NULL,
    original_filename VARCHAR(512) NULL,
    content_type VARCHAR(255) NULL,
    byte_size BIGINT NOT NULL DEFAULT 0,
    sha256 CHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'available',
    visibility VARCHAR(32) NOT NULL DEFAULT 'private',
    metadata_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    UNIQUE KEY uq_artifact_objects_uuid (artifact_uuid),
    KEY idx_artifact_objects_owner_type (owner_user_id, artifact_type),
    KEY idx_artifact_objects_session (generation_session_id),
    KEY idx_artifact_objects_article (generated_article_id),
    KEY idx_artifact_objects_source (knowledge_source_id),
    CONSTRAINT fk_artifact_objects_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_artifact_objects_session FOREIGN KEY (generation_session_id) REFERENCES generation_sessions(id) ON DELETE SET NULL,
    CONSTRAINT fk_artifact_objects_article FOREIGN KEY (generated_article_id) REFERENCES generated_articles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS billing_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    owner_user_id BIGINT NOT NULL,
    generation_session_id BIGINT NULL,
    generated_article_id BIGINT NULL,
    provider_id BIGINT NULL,
    model_catalog_id BIGINT NULL,
    provider_code VARCHAR(64) NULL,
    model VARCHAR(128) NOT NULL,
    module_key VARCHAR(64) NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cost_cny DECIMAL(14, 8) NOT NULL DEFAULT 0,
    usage_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_billing_records_owner_created (owner_user_id, created_at),
    KEY idx_billing_records_session (generation_session_id),
    KEY idx_billing_records_model_created (model, created_at),
    CONSTRAINT fk_billing_records_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_billing_records_session FOREIGN KEY (generation_session_id) REFERENCES generation_sessions(id) ON DELETE SET NULL,
    CONSTRAINT fk_billing_records_article FOREIGN KEY (generated_article_id) REFERENCES generated_articles(id) ON DELETE SET NULL,
    CONSTRAINT fk_billing_records_provider FOREIGN KEY (provider_id) REFERENCES model_providers(id) ON DELETE SET NULL,
    CONSTRAINT fk_billing_records_catalog FOREIGN KEY (model_catalog_id) REFERENCES model_catalog(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    owner_user_id BIGINT NULL,
    email VARCHAR(255) NULL,
    action VARCHAR(128) NOT NULL,
    ip_address VARCHAR(128) NULL,
    user_agent VARCHAR(512) NULL,
    detail_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_audit_events_created (created_at),
    KEY idx_audit_events_owner_created (owner_user_id, created_at),
    KEY idx_audit_events_action_created (action, created_at),
    CONSTRAINT fk_audit_events_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    owner_user_id BIGINT NOT NULL,
    slug VARCHAR(128) NOT NULL,
    label VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    description TEXT NULL,
    metadata_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    UNIQUE KEY uq_knowledge_bases_owner_slug (owner_user_id, slug),
    KEY idx_knowledge_bases_owner_status (owner_user_id, status),
    CONSTRAINT fk_knowledge_bases_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS vector_collections (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    knowledge_base_id BIGINT NOT NULL,
    backend VARCHAR(64) NOT NULL DEFAULT 'chroma',
    collection_name VARCHAR(255) NOT NULL,
    embedding_model VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    metadata_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_vector_collections_backend_name (backend, collection_name),
    UNIQUE KEY uq_vector_collections_kb_backend (knowledge_base_id, backend),
    CONSTRAINT fk_vector_collections_kb FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    knowledge_base_id BIGINT NOT NULL,
    owner_user_id BIGINT NOT NULL,
    original_artifact_id BIGINT NULL,
    parsed_artifact_id BIGINT NULL,
    original_filename VARCHAR(512) NOT NULL,
    content_type VARCHAR(255) NULL,
    byte_size BIGINT NOT NULL DEFAULT 0,
    sha256 CHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
    error_summary TEXT NULL,
    metadata_json JSON NULL,
    indexed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    KEY idx_knowledge_sources_kb_status (knowledge_base_id, status),
    KEY idx_knowledge_sources_owner_created (owner_user_id, created_at),
    CONSTRAINT fk_knowledge_sources_kb FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    CONSTRAINT fk_knowledge_sources_owner FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_knowledge_sources_original_artifact FOREIGN KEY (original_artifact_id) REFERENCES artifact_objects(id) ON DELETE SET NULL,
    CONSTRAINT fk_knowledge_sources_parsed_artifact FOREIGN KEY (parsed_artifact_id) REFERENCES artifact_objects(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    knowledge_source_id BIGINT NOT NULL,
    knowledge_base_id BIGINT NOT NULL,
    vector_collection_id BIGINT NULL,
    chunk_key VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    content_sha256 CHAR(64) NULL,
    char_start INT NULL,
    char_end INT NULL,
    token_count INT NULL,
    chroma_id VARCHAR(255) NULL,
    metadata_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'indexed',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_knowledge_chunks_source_index (knowledge_source_id, chunk_index),
    KEY idx_knowledge_chunks_kb_status (knowledge_base_id, status),
    KEY idx_knowledge_chunks_chroma_id (chroma_id),
    CONSTRAINT fk_knowledge_chunks_source FOREIGN KEY (knowledge_source_id) REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    CONSTRAINT fk_knowledge_chunks_kb FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    CONSTRAINT fk_knowledge_chunks_collection FOREIGN KEY (vector_collection_id) REFERENCES vector_collections(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO roles(code, display_name, description) VALUES
    ('user', 'User', 'Default authenticated user'),
    ('admin', 'Admin', 'Administrative user');

INSERT IGNORE INTO model_providers(
    code, display_name, provider_type, base_url, auth_mode,
    supports_openai_compat, supports_streaming, supports_search, supports_vision, enabled, config_json
) VALUES
    ('dashscope', 'DashScope/Bailian', 'openai_compatible', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'api_key', 1, 1, 1, 1, 1, JSON_OBJECT('default', true)),
    ('deepseek', 'DeepSeek', 'openai_compatible', 'https://api.deepseek.com', 'api_key', 1, 1, 0, 0, 0, JSON_OBJECT('enabled_when_credentials_present', true));

INSERT IGNORE INTO model_catalog(
    provider_id, model_id, display_name, role_key, capabilities_json,
    input_price_per_1k, output_price_per_1k, context_window, enabled, config_json
)
SELECT p.id, seed.model_id, seed.display_name, seed.role_key, seed.capabilities_json,
       seed.input_price, seed.output_price, seed.context_window, seed.enabled, seed.config_json
FROM model_providers p
JOIN (
    SELECT 'dashscope' provider_code, 'qwen3.7-plus' model_id, 'Qwen 3.7 Plus' display_name, 'main_writer' role_key,
           JSON_ARRAY('text', 'streaming') capabilities_json, 0.00080000 input_price, 0.00200000 output_price,
           NULL context_window, 1 enabled, JSON_OBJECT() config_json
    UNION ALL SELECT 'dashscope', 'qwen3.6-flash', 'Qwen 3.6 Flash', 'fast_writer',
           JSON_ARRAY('text', 'streaming'), 0.00030000, 0.00060000, NULL, 1, JSON_OBJECT()
    UNION ALL SELECT 'dashscope', 'qwen3.7-plus', 'Qwen 3.7 Plus', 'web_search',
           JSON_ARRAY('text', 'search', 'streaming'), 0.00080000, 0.00200000, NULL, 1, JSON_OBJECT('enable_search', true)
    UNION ALL SELECT 'dashscope', 'qwen3.7-plus', 'Qwen 3.7 Plus', 'vision_layout',
           JSON_ARRAY('text', 'vision'), 0.00080000, 0.00200000, NULL, 1, JSON_OBJECT()
    UNION ALL SELECT 'dashscope', 'qwen3.6-flash', 'Qwen 3.6 Flash', 'template_planner',
           JSON_ARRAY('text'), 0.00030000, 0.00060000, NULL, 1, JSON_OBJECT()
    UNION ALL SELECT 'dashscope', 'qwen3.6-flash', 'Qwen 3.6 Flash', 'audit_text',
           JSON_ARRAY('text'), 0.00030000, 0.00060000, NULL, 1, JSON_OBJECT()
    UNION ALL SELECT 'dashscope', 'text-embedding-v4', 'Text Embedding v4', 'embedding',
           JSON_ARRAY('embedding'), NULL, NULL, NULL, 1, JSON_OBJECT()
    UNION ALL SELECT 'deepseek', 'deepseek-chat', 'DeepSeek Chat', 'main_writer',
           JSON_ARRAY('text', 'streaming'), NULL, NULL, NULL, 0, JSON_OBJECT('openai_compatible', true)
    UNION ALL SELECT 'deepseek', 'deepseek-reasoner', 'DeepSeek Reasoner', 'main_writer',
           JSON_ARRAY('text', 'reasoning', 'streaming'), NULL, NULL, NULL, 0, JSON_OBJECT('openai_compatible', true)
) seed ON seed.provider_code = p.code;
