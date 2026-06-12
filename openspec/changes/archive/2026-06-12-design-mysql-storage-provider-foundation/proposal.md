## Why

The project currently stores authentication, billing, user preferences, and API keys in local SQLite while generated documents are exposed through local download paths and knowledge vectors live in Chroma. Moving toward MySQL, persistent generated-article history, and future DeepSeek or other model providers requires a clear data/storage boundary before implementation hardens around ad hoc tables or file paths.

## What Changes

- Introduce a MySQL persistence foundation for account, API key, user preference, billing, generation session, generated article, and artifact metadata.
- Define ownership and access rules for users, roles, provider credentials, generation sessions, generated documents, quality reports, and token/cost records.
- Define document artifact storage behavior: binary documents and reports SHALL NOT be stored directly in MySQL except for small metadata; generated files SHALL live in filesystem/object storage, with MySQL storing artifact records, storage keys, hashes, sizes, MIME types, and ownership.
- Define how Chroma/vector storage remains responsible for embeddings while MySQL tracks knowledge-base/source metadata and maps sources to vector collections.
- Add a provider configuration model so Aliyun Bailian/DashScope, compatible OpenAI endpoints, DeepSeek, and future platforms can be represented consistently without rewriting generation workflows.
- Prepare backend API and admin/history surfaces to read generated-article history from MySQL-backed records rather than frontend-only mock data in a later implementation step.

## Capabilities

### New Capabilities
- `mysql-persistence-foundation`: Covers MySQL-backed structured data, account tables, roles, user preferences, API keys, billing, generation sessions, and migration expectations from SQLite.
- `artifact-storage-architecture`: Covers generated document/report storage, metadata tables, storage backends, download authorization, and why large binaries should live outside MySQL.
- `model-provider-registry`: Covers provider/model registry design for DashScope/OpenAI-compatible/DeepSeek platforms, user model choices, provider credentials, quota behavior, and future provider extension.
- `knowledge-vector-metadata`: Covers the relationship between MySQL knowledge/source metadata and existing Chroma vector collections so uploaded documents, chunks, and vector indexes remain traceable.

### Modified Capabilities
- None.

## Impact

- Affected backend modules: `core/auth.py`, `core/billing.py`, `core/audit_log.py`, `core/generation_sessions.py`, `core/vector_store.py`, `core/model_router.py`, `core/dashscope_chat.py`, `core/api_key_validation.py`, `server.py`, and `config.py`.
- Affected frontend surfaces: Settings model/API-key configuration, Generate session recovery/download behavior, Admin stats, and History/generated-article dashboards.
- New dependencies likely include a MySQL driver and migration tooling such as SQLAlchemy/Alembic or a project-local migration runner.
- Storage impact: generated `.docx`, reports, extracted source files, and future preview assets should use local filesystem storage in development and object storage in production; MySQL stores metadata and access-control records.
- API impact: future endpoints may expose generated article history, artifact metadata, storage-backed downloads, provider registry data, and admin/user model-provider settings.
