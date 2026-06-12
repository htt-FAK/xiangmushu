## 1. MySQL Foundation and Configuration

- [x] 1.1 Add MySQL persistence configuration in `config.py`, including database URL/host/user/password/name, persistence mode, migration mode, and a SQLite fallback flag for local development.
- [x] 1.2 Add a database access module such as `core/db.py` or `core/persistence.py` that provides connection/session management, transaction boundaries, and health checks for MySQL.
- [x] 1.3 Choose and add the MySQL driver/migration dependency in `requirements.txt`, documenting whether the implementation uses SQLAlchemy/Alembic or a project-local migration runner.
- [x] 1.4 Create initial migration files for users, roles, user roles, email verification codes, user preferences, provider credentials, model providers, model catalog, user model choices, billing records, audit events, generation sessions, generated articles, artifact objects, knowledge bases, knowledge sources, knowledge chunks, and vector collections.
- [x] 1.5 Add a startup schema verification or migration command that can run safely in development and report missing/failed migrations clearly.

## 2. Account, Credential, Billing, and Audit Repositories

- [x] 2.1 Refactor `core/auth.py` persistence calls behind a repository boundary while preserving existing auth behavior and JWT payload compatibility.
- [x] 2.2 Move user language and model choices into MySQL-backed preference records while keeping frontend `fetchUserPreferences` and `updateUserPreferences` response shapes compatible.
- [x] 2.3 Refactor `core/billing.py` to write billing records to MySQL with user, provider/model, session, token, and cost fields.
- [x] 2.4 Refactor user API key storage to encrypted MySQL provider credential records with validation metadata and no plaintext exposure in API responses.
- [x] 2.5 Refactor `core/audit_log.py` and admin stats in `server.py` to read/write MySQL-backed audit and billing records.
- [x] 2.6 Add SQLite-to-MySQL migration scripts for users, preferences, user API keys, billing records, and audit events, including dry-run and duplicate-safe behavior.

## 3. Artifact Storage Backend

- [x] 3.1 Add an artifact storage abstraction under `core/artifacts.py` or `core/storage/` with local filesystem backend methods for put, stream/open, metadata creation, delete/soft-delete, and checksum calculation.
- [x] 3.2 Add configuration for local artifact root and future object storage settings such as backend type, bucket/container, endpoint, region, access key, and secret source.
- [x] 3.3 Add MySQL-backed artifact metadata writes for generated `.docx` documents, quality reports, uploaded source files, parsed markdown, and preview assets.
- [x] 3.4 Replace new generation download paths with artifact-id-backed records while keeping legacy `/api/download/{filename}` compatibility during migration.
- [x] 3.5 Add authorized artifact download endpoints in `server.py` that verify current-user ownership through MySQL metadata before streaming or redirecting.
- [x] 3.6 Add tests for artifact ownership, missing artifact behavior, checksum/size metadata, legacy download compatibility, and path traversal rejection.

## 4. Generation Session and History Persistence

- [x] 4.1 Persist generation session creation, status, progress, params, current task, error summary, timestamps, and billing totals to MySQL from `core/generation_sessions.py` or a new repository.
- [x] 4.2 Persist generated article records when generation completes or enters review/error state, linking them to document/report artifacts and billing totals.
- [x] 4.3 Add backend history endpoints in `server.py` for listing generated articles, filtering/searching by status/text, fetching detail, and returning aggregate token/cost/model usage.
- [x] 4.4 Update `frontend/src/pages/HistoryPage.tsx` and related types/API helpers to use backend history data when available while optionally retaining mock fallback for development.
- [x] 4.5 Update Generate page completion/session recovery to use artifact metadata and persisted session records for document/report download actions.
- [x] 4.6 Add tests for process restart recovery: an existing MySQL-backed running/done session can be fetched after backend restart.

## 5. Knowledge Metadata and Chroma Mapping

- [x] 5.1 Add MySQL tables/repositories for knowledge bases, knowledge sources, parsed artifacts, chunk metadata, and vector collection mappings.
- [x] 5.2 Update knowledge base create/delete/list endpoints in `server.py` to read/write MySQL metadata while preserving current frontend response shapes.
- [x] 5.3 Update knowledge upload/indexing flow to write uploaded source artifacts, parsed text artifacts, source status, chunk metadata, and Chroma collection mapping.
- [x] 5.4 Update `core/vector_store.py` writes so Chroma metadata includes stable MySQL source/chunk identifiers where possible.
- [x] 5.5 Add integrity checks for missing Chroma collections, missing MySQL source rows, and source removal/reindexing behavior.
- [x] 5.6 Add tests for upload, retrieval traceability, source deletion, and Chroma/MySQL metadata consistency.

## 6. Model Provider Registry and DeepSeek Readiness

- [x] 6.1 Add MySQL seed/migration data for current providers and models, including DashScope/OpenAI-compatible endpoints, existing module roles, capabilities, prices, and enabled status.
- [x] 6.2 Add provider/model repository functions used by `core/model_router.py`, Settings APIs, and generation modules.
- [x] 6.3 Refactor provider-specific request shaping in `core/dashscope_chat.py` or a new provider adapter module so DashScope and DeepSeek options are isolated from caller modules.
- [x] 6.4 Add DeepSeek provider/model registry support without forcing it enabled when credentials are absent or quota is unavailable.
- [x] 6.5 Update API key validation to validate credentials by provider and return normalized validation/probe results.
- [x] 6.6 Update frontend Settings provider/model UI data loading to use registry-backed provider/model options and handle disabled or unavailable selected models.
- [x] 6.7 Add tests for provider registry loading, user model choice validation, disabled model fallback, quota error normalization, and DeepSeek-compatible adapter request options.

## 7. Verification and Rollout

- [x] 7.1 Run backend unit tests covering auth, billing, API keys, provider errors, generation sessions, knowledge metadata, and artifact downloads.
- [x] 7.2 Run a MySQL integration smoke test that creates a user, saves preferences/key metadata, uploads a knowledge source, runs or mocks a generation, stores artifacts, and reads history.
- [x] 7.3 Run `npm run build` in `frontend` and fix TypeScript/Vite issues from API/type changes.
- [x] 7.4 Use Playwright to verify Settings provider selection, Generate document/report download actions, and History backend records on desktop and mobile.
- [x] 7.5 Document local development setup for MySQL mode, SQLite fallback, local artifact storage, and future object storage environment variables.
- [x] 7.6 Document production recommendation: use MySQL for metadata and an object storage bucket for generated/uploaded files, not direct MySQL binary storage.
