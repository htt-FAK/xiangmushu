INSERT INTO model_providers(
    code,
    display_name,
    provider_type,
    base_url,
    auth_mode,
    supports_openai_compat,
    supports_streaming,
    supports_search,
    supports_vision,
    enabled,
    config_json
)
VALUES(
    'mimo',
    'Xiaomi MiMo',
    'openai_compatible',
    'https://api.xiaomimimo.com/v1',
    'api_key',
    1,
    1,
    1,
    1,
    0,
    JSON_OBJECT('enabled_when_credentials_present', TRUE)
)
ON DUPLICATE KEY UPDATE
    display_name = VALUES(display_name),
    provider_type = VALUES(provider_type),
    base_url = VALUES(base_url),
    auth_mode = VALUES(auth_mode),
    supports_openai_compat = VALUES(supports_openai_compat),
    supports_streaming = VALUES(supports_streaming),
    supports_search = VALUES(supports_search),
    supports_vision = VALUES(supports_vision),
    config_json = VALUES(config_json);
