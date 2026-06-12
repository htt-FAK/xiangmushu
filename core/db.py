from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Any, Iterator

import config

LOG = logging.getLogger(__name__)


class DatabaseConfigurationError(RuntimeError):
    """Raised when the configured persistence backend cannot be used."""


@dataclass(frozen=True)
class MySQLSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout: float = 5
    read_timeout: float = 30
    write_timeout: float = 30


def persistence_mode() -> str:
    return (config.PERSISTENCE_MODE or "sqlite").strip().lower()


def mysql_enabled() -> bool:
    return persistence_mode() == "mysql"


def mysql_settings() -> MySQLSettings:
    return MySQLSettings(
        host=config.MYSQL_HOST,
        port=int(config.MYSQL_PORT),
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset=config.MYSQL_CHARSET,
        connect_timeout=float(config.MYSQL_CONNECT_TIMEOUT),
        read_timeout=float(config.MYSQL_READ_TIMEOUT),
        write_timeout=float(config.MYSQL_WRITE_TIMEOUT),
    )


def mysql_configured() -> bool:
    settings = mysql_settings()
    return bool(settings.host and settings.user and settings.database)


def _pymysql():
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as exc:
        raise DatabaseConfigurationError(
            "MySQL persistence requires PyMySQL. Install dependencies with `pip install -r requirements.txt`."
        ) from exc
    return pymysql, DictCursor


def connect_mysql(*, database: str | None = None):
    if not mysql_configured():
        raise DatabaseConfigurationError(
            "MySQL is not fully configured. Set MYSQL_HOST, MYSQL_USER, and MYSQL_DATABASE."
        )
    pymysql, cursor_class = _pymysql()
    settings = mysql_settings()
    kwargs: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "user": settings.user,
        "password": settings.password,
        "charset": settings.charset,
        "cursorclass": cursor_class,
        "autocommit": False,
        "connect_timeout": settings.connect_timeout,
        "read_timeout": settings.read_timeout,
        "write_timeout": settings.write_timeout,
    }
    selected_database = settings.database if database is None else database
    if selected_database:
        kwargs["database"] = selected_database
    return pymysql.connect(**kwargs)


@contextmanager
def mysql_transaction() -> Iterator[Any]:
    conn = connect_mysql()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mysql_health_check() -> dict[str, Any]:
    if not mysql_enabled():
        return {"ok": True, "mode": persistence_mode(), "mysql": False}
    try:
        with connect_mysql() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                row = cur.fetchone()
        return {"ok": bool(row and row.get("ok") == 1), "mode": "mysql", "mysql": True}
    except Exception as exc:
        return {"ok": False, "mode": "mysql", "mysql": True, "error": str(exc)}


def _quote_identifier(value: str) -> str:
    cleaned = value.replace("`", "``")
    return f"`{cleaned}`"


def ensure_database_exists() -> None:
    if not mysql_enabled():
        return
    settings = mysql_settings()
    if not config.MYSQL_AUTO_CREATE_DATABASE:
        return
    with connect_mysql(database="") as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS {_quote_identifier(settings.database)} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()


def migration_files() -> list[Path]:
    root = Path(config.MYSQL_MIGRATIONS_DIR)
    if not root.exists():
        return []
    return sorted(path for path in root.glob("*.sql") if path.is_file())


def _split_sql_script(script: str) -> list[str]:
    cleaned_lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("#"):
            continue
        cleaned_lines.append(line)
    script = "\n".join(cleaned_lines)
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escape = False
    for char in script:
        current.append(char)
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement[:-1].strip())
            current = []
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return [stmt for stmt in statements if stmt]


def _ensure_migration_table(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                filename VARCHAR(255) NOT NULL UNIQUE,
                checksum CHAR(64) NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )


def _applied_migrations(conn: Any) -> set[str]:
    _ensure_migration_table(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations")
        return {str(row["filename"]) for row in cur.fetchall()}


def run_mysql_migrations() -> list[str]:
    if not mysql_enabled():
        return []
    ensure_database_exists()
    import hashlib

    applied_now: list[str] = []
    files = migration_files()
    with mysql_transaction() as conn:
        applied = _applied_migrations(conn)
        for path in files:
            if path.name in applied:
                continue
            script = path.read_text(encoding="utf-8")
            statements = _split_sql_script(script)
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
                checksum = hashlib.sha256(script.encode("utf-8")).hexdigest()
                cur.execute(
                    "INSERT INTO schema_migrations(filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
            applied_now.append(path.name)
    if applied_now:
        LOG.info("Applied MySQL migrations: %s", ", ".join(applied_now))
    return applied_now


def ensure_configured_database() -> dict[str, Any]:
    if not mysql_enabled():
        return {"ok": True, "mode": persistence_mode(), "migrations": []}
    if not mysql_configured():
        if config.PERSISTENCE_SQLITE_FALLBACK:
            LOG.warning("PERSISTENCE_MODE=mysql but MySQL is not configured; SQLite fallback remains available.")
            return {"ok": False, "mode": "mysql", "fallback": "sqlite", "migrations": []}
        raise DatabaseConfigurationError("PERSISTENCE_MODE=mysql but MySQL configuration is incomplete.")
    migrations: list[str] = []
    if config.MYSQL_AUTO_MIGRATE:
        migrations = run_mysql_migrations()
    health = mysql_health_check()
    if not health.get("ok") and not config.PERSISTENCE_SQLITE_FALLBACK:
        raise DatabaseConfigurationError(str(health.get("error") or "MySQL health check failed"))
    return {"ok": bool(health.get("ok")), "mode": "mysql", "migrations": migrations, "health": health}


def mysql_database_url(mask_password: bool = True) -> str:
    settings = mysql_settings()
    password = "***" if mask_password and settings.password else settings.password
    return (
        f"mysql+pymysql://{settings.user}:{password}@"
        f"{settings.host}:{settings.port}/{settings.database}?charset={settings.charset}"
    )


if os.getenv("APP_CONSOLE_LOG", "").strip().lower() in {"1", "true", "yes"}:
    logging.basicConfig(level=logging.INFO)
