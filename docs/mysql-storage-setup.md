# MySQL and Artifact Storage Setup

This project keeps the current SQLite path as a compatibility fallback and adds a MySQL schema path for durable structured records.

## Persistence Modes

- `PERSISTENCE_MODE=sqlite`: current local development mode.
- `PERSISTENCE_MODE=mysql`: enables MySQL configuration, schema health checks, and migrations.
- `PERSISTENCE_SQLITE_FALLBACK=1`: allows the app to continue reporting a recoverable MySQL configuration problem during migration instead of failing hard.

## Migration Tooling

The implementation uses `PyMySQL` plus a small project-local migration runner in `core/db.py`.

It does not use SQLAlchemy/Alembic yet because the first milestone needs a low-risk schema foundation without refactoring all repositories at once. Migrations live in `migrations/mysql/*.sql` and are tracked in the MySQL `schema_migrations` table by filename and checksum.

Run checks:

```powershell
python scripts/mysql_migrate.py --check
```

Apply migrations:

```powershell
$env:PERSISTENCE_MODE="mysql"
python scripts/mysql_migrate.py --migrate
```

The FastAPI startup path also calls `ensure_configured_database()`. When `MYSQL_AUTO_MIGRATE=1`, pending migrations are applied before the app serves requests.

## Storage Boundary

MySQL stores users, preferences, provider credentials, billing, generation sessions, generated article history, artifact metadata, provider/model registry rows, and knowledge/vector metadata.

Generated `.docx` files, reports, uploaded source files, parsed markdown, previews, and other large artifacts should live in local artifact storage for development or object storage such as Tencent COS in production. MySQL stores only metadata such as owner, backend, bucket, object key, filename, content type, size, checksum, status, and timestamps.

Recommended production shape:

```text
MySQL
  structured records + artifact metadata + ownership

Tencent COS / object storage
  generated documents + reports + uploads + previews

Chroma
  vector embeddings and nearest-neighbor index
```
