## Context

The current backend uses SQLite through `core/auth.py`, `core/billing.py`, and `core/audit_log.py` for users, email verification codes, billing records, and user API keys. Generation sessions are currently process-memory snapshots in `core/generation_sessions.py`, generated files are written under the configured output directory and downloaded by filename, and knowledge embeddings are persisted in Chroma collections named from the knowledge-base slug.

The product direction now needs durable MySQL-backed accounts and history, safer artifact ownership, historical generated-article download pages, and a model-provider structure that can grow from the current DashScope/OpenAI-compatible setup to DeepSeek and other platforms.

## Goals / Non-Goals

**Goals:**

- Move structured business data from SQLite-style tables to MySQL tables with explicit schema ownership and migrations.
- Keep user accounts, roles, preferences, provider credentials, billing, generation sessions, generated articles, artifacts, and knowledge metadata queryable from MySQL.
- Keep document binaries, reports, uploaded source files, previews, and derived assets outside MySQL in filesystem/object storage.
- Preserve Chroma as the vector index while making MySQL the source of truth for knowledge bases, uploaded sources, chunk metadata, and vector collection mapping.
- Add a provider registry that can represent DashScope, OpenAI-compatible gateways, DeepSeek, and future model providers without hardcoding provider-specific behavior across generation modules.
- Support incremental migration and a development fallback path so the system can be tested before production object storage is available.

**Non-Goals:**

- Replacing Chroma with MySQL vector search.
- Storing large `.docx`, `.pdf`, image, report, or uploaded-source binaries directly inside MySQL.
- Implementing every future provider integration in this change; DeepSeek readiness means the schema and routing abstraction can represent it.
- Rewriting the generation pipeline or prompt logic beyond the persistence/provider boundaries needed for the new architecture.

## Decisions

### Decision 1: MySQL stores structured data and artifact metadata, not large binaries

Generated documents and reports should be stored in a storage backend. MySQL should store only metadata: artifact id, owner, generation session, article id, type, storage backend, bucket/container, object key, filename, MIME type, byte size, checksum, visibility, created time, and deletion state.

Recommended table family:

```text
users
roles
user_roles
email_verification_codes
user_preferences
provider_credentials
model_providers
model_catalog
user_model_choices
generation_sessions
generated_articles
artifact_objects
billing_records
audit_events
knowledge_bases
knowledge_sources
knowledge_chunks
vector_collections
```

Alternative considered: store `.docx` and report content in `LONGBLOB` columns. This simplifies backup at first, but it bloats database storage, slows backups and restores, complicates CDN/object access, and makes downloads compete with transactional queries. It is a poor fit for generated files and uploaded reference documents.

### Decision 2: Use pluggable artifact storage with local filesystem first and object storage next

Define an artifact storage interface with at least:

```text
put(bytes_or_path, metadata) -> ArtifactObject
open/artifact_stream(artifact_id, user) -> stream
presign_or_download_url(artifact_id, user) -> url/path
delete_or_mark_deleted(artifact_id, user)
```

Development can use a local backend such as `data/artifacts/{user_id}/{artifact_id}/...`. Production can use OSS/S3/MinIO buckets. MySQL records must not expose raw absolute paths to the frontend; downloads should use artifact ids and authorization checks.

Recommended artifact object fields:

```text
id BIGINT / UUID
owner_user_id
generation_session_id NULL
generated_article_id NULL
knowledge_source_id NULL
artifact_type ENUM('generated_doc','quality_report','uploaded_source','source_markdown','preview_image','other')
storage_backend ENUM('local','oss','s3','minio')
bucket_name NULL
object_key
original_filename
content_type
byte_size
sha256
status ENUM('available','deleted','failed')
created_at
deleted_at NULL
```

### Decision 3: MySQL becomes the source of truth for generation history

`generation_sessions` should persist the session lifecycle that is now in memory: status, current step, progress, params, selected template, selected knowledge base, error summary, billing totals, and timestamps. `generated_articles` should represent the user-facing completed or reviewable document record shown in the history page. `artifact_objects` links documents and reports to either sessions or articles.

High-level flow:

```text
User starts generation
  -> generation_sessions row created
  -> streaming events update progress/session snapshots
  -> Word/report files written to artifact storage
  -> artifact_objects rows created
  -> generated_articles row created/updated
  -> billing_records rows linked to session/article/provider/model
  -> frontend history queries generated_articles + artifact metadata
```

### Decision 4: Keep Chroma for vectors, track metadata in MySQL

Chroma should keep embeddings and nearest-neighbor search. MySQL should track knowledge base ownership, upload source records, parsed source assets, chunk ids, and collection names. Chroma metadata should include stable MySQL ids where possible, such as `knowledge_source_id` and `knowledge_chunk_id`, so retrieval results can be traced back to source rows.

Alternative considered: migrate vectors into MySQL immediately. That would create more risk and poorer vector-search ergonomics unless a dedicated MySQL vector extension and benchmark exist. The safer architecture is MySQL for metadata and Chroma for vector index.

### Decision 5: Add a provider registry rather than hardcoding DeepSeek conditionals

Model/provider setup should be data-driven:

```text
model_providers
  id, code, display_name, provider_type, base_url, auth_mode, supports_openai_compat,
  supports_streaming, supports_search, supports_vision, enabled, config_json

model_catalog
  id, provider_id, model_id, display_name, role, capabilities_json,
  input_price_per_1k, output_price_per_1k, context_window, enabled

provider_credentials
  id, owner_user_id NULL, provider_id, encrypted_api_key, scopes_json, status, validated_at

user_model_choices
  user_id, module_key, provider_id, model_catalog_id
```

Provider-specific request shaping should remain in a narrow adapter layer. For example, DashScope compatible mode and DeepSeek `thinking` flags can be handled by provider adapters while `core/generator.py`, `core/template_analyzer.py`, and audit modules ask for a client/model by role.

### Decision 6: Introduce migrations before replacing SQLite calls

Use either SQLAlchemy/Alembic or a small project-local migration runner. The key requirement is a repeatable, versioned MySQL schema with forward migrations and smoke tests. Existing SQLite data should be migrated through scripts that read current tables and write MySQL rows with normalized timestamps and encrypted credentials preserved or re-encrypted.

## Risks / Trade-offs

- MySQL migration touches auth, billing, settings, admin stats, history, and generation session recovery -> Mitigate with a repository layer and tests that run against temporary SQLite/MySQL-like fixtures where possible, plus a dedicated MySQL integration smoke test.
- Object storage may not be available during early development -> Mitigate with a local artifact backend that uses the same interface and MySQL metadata shape.
- Provider registry can become too abstract too soon -> Mitigate by modeling only current roles/modules and known providers first, while leaving JSON capability fields for provider-specific metadata.
- Chroma and MySQL metadata can drift -> Mitigate by storing stable source/chunk ids in Chroma metadata and adding integrity checks for missing collections or missing chunk rows.
- Download URLs may leak file paths or bypass ownership -> Mitigate by using artifact ids, current-user authorization, and server-side streaming/presigned URLs instead of raw filename-only access.

## Migration Plan

1. Add MySQL configuration and database access layer while keeping existing SQLite code path available for development fallback.
2. Create initial MySQL migrations for users, roles, preferences, API keys, billing, sessions, generated articles, artifacts, providers, models, and knowledge metadata.
3. Add migration/export scripts from existing SQLite tables to MySQL.
4. Add local artifact storage backend and metadata writes for generated docs/reports.
5. Change download endpoints from `/api/download/{filename}` toward artifact-id-backed access while retaining compatibility for existing local files during transition.
6. Persist generation sessions and generated article records to MySQL.
7. Replace frontend mock history data with backend history endpoints.
8. Add provider/model registry APIs and use them from Settings and generation routing.
9. Validate MySQL mode with integration smoke tests, then deprecate direct SQLite persistence.

Rollback: keep the SQLite/local-file mode gated by configuration until MySQL migrations, artifact storage, and history endpoints are verified. Artifact files created in local/object storage remain valid because MySQL stores metadata rather than the only copy of binary content.

## Open Questions

- Which object storage will be used in production: Aliyun OSS, S3-compatible MinIO, Tencent COS, or another bucket service?
- Should provider credentials be platform-wide, user-owned, or both, and should users be allowed to bring different provider keys per provider?
- Should generated article history be retained forever, soft-deleted, or governed by a retention policy per user/team?
- Will accounts remain single-user ownership, or should the schema include organizations/workspaces now?
- Should billing prices come from static config, provider registry tables, or both with config as seed data?
