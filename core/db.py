from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from typing import Any, Iterator

import config

LOG = logging.getLogger(__name__)


def _decode_json_field(value: Any) -> Any:
    """Decode JSON columns from MySQL / SQLite in an idempotent way.

    MySQL drivers may return JSON columns as:
    - raw JSON strings (most common)
    - already-decoded Python lists/dicts (driver/version dependent)
    - bytes

    This helper accepts all three so callers don't need to care.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


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


# ============================================================================
# Custom Models CRUD Methods
# ============================================================================

@dataclass
class CustomModel:
    """Data class for custom AI models"""
    id: int
    user_id: int
    name: str
    base_url: str
    model_id: str
    encrypted_api_key: str
    api_key_hint: str | None
    capabilities_json: list[str] | None
    assigned_roles_json: list[str] | None
    default_model_id: str | None
    status: str
    last_tested_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str


def create_custom_model(
    user_id: int,
    name: str,
    base_url: str,
    model_id: str,
    encrypted_api_key: str,
    api_key_hint: str | None,
    capabilities_json: list[str] | None = None,
    assigned_roles_json: list[str] | None = None,
    default_model_id: str | None = None,
    status: str = "untested"
) -> CustomModel:
    """
    Create a new custom model for a user.
    
    Args:
        user_id: User ID who owns this model
        name: Display name for the model
        base_url: API base URL
        model_id: Model identifier
        encrypted_api_key: Encrypted API key
        api_key_hint: Masked API key hint (e.g., "sk-a1...ef")
        capabilities_json: List of detected capabilities (optional)
        assigned_roles_json: List of assigned roles (optional)
        default_model_id: Default model ID for this entry (optional)
        status: Model status (default: "untested")
    
    Returns:
        CustomModel object with the created record
    
    Raises:
        DatabaseConfigurationError: If database is not configured or operation fails
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_custom_models 
                    (user_id, name, base_url, model_id, encrypted_api_key, api_key_hint,
                     capabilities_json, assigned_roles_json, default_model_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id, name, base_url, model_id, encrypted_api_key, api_key_hint,
                        json.dumps(capabilities_json) if capabilities_json else None,
                        json.dumps(assigned_roles_json) if assigned_roles_json else None,
                        default_model_id, status
                    )
                )
                model_id_created = cur.lastrowid
                
                # Fetch the created record
                cur.execute(
                    """
                    SELECT * FROM user_custom_models WHERE id = %s
                    """,
                    (model_id_created,)
                )
                row = cur.fetchone()
        
        return CustomModel(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            base_url=row['base_url'],
            model_id=row['model_id'],
            encrypted_api_key=row['encrypted_api_key'],
            api_key_hint=row['api_key_hint'],
            capabilities_json=_decode_json_field(row['capabilities_json']),
            assigned_roles_json=_decode_json_field(row['assigned_roles_json']),
            default_model_id=row['default_model_id'],
            status=row['status'],
            last_tested_at=row['last_tested_at'].isoformat() if row['last_tested_at'] else None,
            last_error=row['last_error'],
            created_at=row['created_at'].isoformat() if row['created_at'] else None,
            updated_at=row['updated_at'].isoformat() if row['updated_at'] else None
        )
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_custom_models 
                (user_id, name, base_url, model_id, encrypted_api_key, api_key_hint,
                 capabilities_json, assigned_roles_json, default_model_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, name, base_url, model_id, encrypted_api_key, api_key_hint,
                    json.dumps(capabilities_json) if capabilities_json else None,
                    json.dumps(assigned_roles_json) if assigned_roles_json else None,
                    default_model_id, status,
                    iso(utc_now()), iso(utc_now())
                )
            )
            conn.commit()
            model_id_created = cursor.lastrowid
            
            cursor.execute(
                """
                SELECT * FROM user_custom_models WHERE id = ?
                """,
                (model_id_created,)
            )
            row = cursor.fetchone()
        
        return CustomModel(
            id=row[0],
            user_id=row[1],
            name=row[2],
            base_url=row[3],
            model_id=row[4],
            encrypted_api_key=row[5],
            api_key_hint=row[6],
            capabilities_json=_decode_json_field(row[7]),
            assigned_roles_json=_decode_json_field(row[8]),
            default_model_id=row[9],
            status=row[10],
            last_tested_at=row[11],
            last_error=row[12],
            created_at=row[13],
            updated_at=row[14]
        )


def get_custom_models_by_user(user_id: int) -> list[CustomModel]:
    """
    Get all custom models for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        List of CustomModel objects (empty list if none found)
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM user_custom_models 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                    """,
                    (user_id,)
                )
                rows = cur.fetchall()
        
        return [
            CustomModel(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                base_url=row['base_url'],
                model_id=row['model_id'],
                encrypted_api_key=row['encrypted_api_key'],
                api_key_hint=row['api_key_hint'],
                capabilities_json=_decode_json_field(row['capabilities_json']),
                assigned_roles_json=_decode_json_field(row['assigned_roles_json']),
                default_model_id=row['default_model_id'],
                status=row['status'],
                last_tested_at=row['last_tested_at'].isoformat() if row['last_tested_at'] else None,
                last_error=row['last_error'],
                created_at=row['created_at'].isoformat() if row['created_at'] else None,
                updated_at=row['updated_at'].isoformat() if row['updated_at'] else None
            )
            for row in rows
        ]
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_custom_models 
                WHERE user_id = ? 
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
        
        return [
            CustomModel(
                id=row[0],
                user_id=row[1],
                name=row[2],
                base_url=row[3],
                model_id=row[4],
                encrypted_api_key=row[5],
                api_key_hint=row[6],
                capabilities_json=_decode_json_field(row[7]),
                assigned_roles_json=_decode_json_field(row[8]),
                default_model_id=row[9],
                status=row[10],
                last_tested_at=row[11],
                last_error=row[12],
                created_at=row[13],
                updated_at=row[14]
            )
            for row in rows
        ]


def get_custom_model_by_id(model_id: int, user_id: int) -> CustomModel | None:
    """
    Get a specific custom model by ID and user ID.
    
    Args:
        model_id: Model ID
        user_id: User ID (for security - only return models owned by this user)
    
    Returns:
        CustomModel object or None if not found or not owned by user
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM user_custom_models 
                    WHERE id = %s AND user_id = %s
                    """,
                    (model_id, user_id)
                )
                row = cur.fetchone()
        
        if row is None:
            return None
        
        return CustomModel(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            base_url=row['base_url'],
            model_id=row['model_id'],
            encrypted_api_key=row['encrypted_api_key'],
            api_key_hint=row['api_key_hint'],
            capabilities_json=_decode_json_field(row['capabilities_json']),
            assigned_roles_json=_decode_json_field(row['assigned_roles_json']),
            default_model_id=row['default_model_id'],
            status=row['status'],
            last_tested_at=row['last_tested_at'].isoformat() if row['last_tested_at'] else None,
            last_error=row['last_error'],
            created_at=row['created_at'].isoformat() if row['created_at'] else None,
            updated_at=row['updated_at'].isoformat() if row['updated_at'] else None
        )
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_custom_models 
                WHERE id = ? AND user_id = ?
                """,
                (model_id, user_id)
            )
            row = cursor.fetchone()
        
        if row is None:
            return None
        
        return CustomModel(
            id=row[0],
            user_id=row[1],
            name=row[2],
            base_url=row[3],
            model_id=row[4],
            encrypted_api_key=row[5],
            api_key_hint=row[6],
            capabilities_json=_decode_json_field(row[7]),
            assigned_roles_json=_decode_json_field(row[8]),
            default_model_id=row[9],
            status=row[10],
            last_tested_at=row[11],
            last_error=row[12],
            created_at=row[13],
            updated_at=row[14]
        )


def update_custom_model(
    model_id: int,
    user_id: int,
    **kwargs
) -> CustomModel | None:
    """
    Update a custom model. Only updates provided fields.
    
    Args:
        model_id: Model ID
        user_id: User ID (for security - only update models owned by this user)
        **kwargs: Fields to update (name, base_url, model_id, encrypted_api_key, 
                  api_key_hint, capabilities_json, assigned_roles_json, 
                  default_model_id, status, last_tested_at, last_error)
    
    Returns:
        Updated CustomModel object or None if not found or not owned by user
    
    Raises:
        ValueError: If no fields provided for update
    """
    if not kwargs:
        raise ValueError("No fields provided for update")
    
    # Build dynamic update query
    allowed_fields = {
        'name', 'base_url', 'model_id', 'encrypted_api_key', 'api_key_hint',
        'capabilities_json', 'assigned_roles_json', 'default_model_id',
        'status', 'last_tested_at', 'last_error'
    }
    
    update_fields = []
    update_values = []
    
    for field in allowed_fields:
        if field in kwargs:
            if field in ['capabilities_json', 'assigned_roles_json']:
                update_fields.append(f"{field} = %s")
                update_values.append(json.dumps(kwargs[field]) if kwargs[field] else None)
            else:
                update_fields.append(f"{field} = %s")
                update_values.append(kwargs[field])
    
    if not update_fields:
        raise ValueError("No valid fields provided for update")
    
    # Add updated_at to the update
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                query = f"""
                    UPDATE user_custom_models 
                    SET {', '.join(update_fields)}, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                """
                cur.execute(query, update_values + [model_id, user_id])
                affected = cur.rowcount
        
        if affected == 0:
            return None
        
        return get_custom_model_by_id(model_id, user_id)
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            query = f"""
                UPDATE user_custom_models 
                SET {', '.join(update_fields)}, updated_at = ?
                WHERE id = ? AND user_id = ?
            """
            cursor.execute(query, update_values + [iso(utc_now()), model_id, user_id])
            conn.commit()
            affected = cursor.rowcount
        
        if affected == 0:
            return None
        
        return get_custom_model_by_id(model_id, user_id)


def delete_custom_model(model_id: int, user_id: int) -> bool:
    """
    Delete a custom model.
    
    Args:
        model_id: Model ID
        user_id: User ID (for security - only delete models owned by this user)
    
    Returns:
        True if deleted, False if not found or not owned by user
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_custom_models 
                    WHERE id = %s AND user_id = %s
                    """,
                    (model_id, user_id)
                )
                affected = cur.rowcount
        
        return affected > 0
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM user_custom_models 
                WHERE id = ? AND user_id = ?
                """,
                (model_id, user_id)
            )
            conn.commit()
            affected = cursor.rowcount
        
        return affected > 0


def get_custom_models_by_capability(user_id: int, capability: str) -> list[CustomModel]:
    """
    Get custom models that have a specific capability.
    
    Args:
        user_id: User ID
        capability: Capability to filter by (e.g., "text", "vision", "embedding")
    
    Returns:
        List of CustomModel objects that have the specified capability
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM user_custom_models 
                    WHERE user_id = %s 
                    AND capabilities_json IS NOT NULL
                    AND JSON_CONTAINS(capabilities_json, %s, '$')
                    ORDER BY created_at DESC
                    """,
                    (user_id, json.dumps(capability))
                )
                rows = cur.fetchall()
        
        return [
            CustomModel(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                base_url=row['base_url'],
                model_id=row['model_id'],
                encrypted_api_key=row['encrypted_api_key'],
                api_key_hint=row['api_key_hint'],
                capabilities_json=_decode_json_field(row['capabilities_json']),
                assigned_roles_json=_decode_json_field(row['assigned_roles_json']),
                default_model_id=row['default_model_id'],
                status=row['status'],
                last_tested_at=row['last_tested_at'].isoformat() if row['last_tested_at'] else None,
                last_error=row['last_error'],
                created_at=row['created_at'].isoformat() if row['created_at'] else None,
                updated_at=row['updated_at'].isoformat() if row['updated_at'] else None
            )
            for row in rows
        ]
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_custom_models 
                WHERE user_id = ? 
                AND capabilities_json IS NOT NULL
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
        
        result = []
        for row in rows:
            caps = _decode_json_field(row[7]) or []
            if capability in caps:
                result.append(CustomModel(
                    id=row[0],
                    user_id=row[1],
                    name=row[2],
                    base_url=row[3],
                    model_id=row[4],
                    encrypted_api_key=row[5],
                    api_key_hint=row[6],
                    capabilities_json=caps,
                    assigned_roles_json=_decode_json_field(row[8]),
                    default_model_id=row[9],
                    status=row[10],
                    last_tested_at=row[11],
                    last_error=row[12],
                    created_at=row[13],
                    updated_at=row[14]
                ))
        
        return result


def get_custom_models_by_role(user_id: int, role: str) -> list[CustomModel]:
    """
    Get custom models that have a specific role assigned.
    
    Args:
        user_id: User ID
        role: Role to filter by (e.g., "text-gen", "vision", "embedding", "audit")
    
    Returns:
        List of CustomModel objects that have the specified role assigned
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM user_custom_models 
                    WHERE user_id = %s 
                    AND assigned_roles_json IS NOT NULL
                    AND JSON_CONTAINS(assigned_roles_json, %s, '$')
                    ORDER BY created_at DESC
                    """,
                    (user_id, json.dumps(role))
                )
                rows = cur.fetchall()
        
        return [
            CustomModel(
                id=row['id'],
                user_id=row['user_id'],
                name=row['name'],
                base_url=row['base_url'],
                model_id=row['model_id'],
                encrypted_api_key=row['encrypted_api_key'],
                api_key_hint=row['api_key_hint'],
                capabilities_json=_decode_json_field(row['capabilities_json']),
                assigned_roles_json=_decode_json_field(row['assigned_roles_json']),
                default_model_id=row['default_model_id'],
                status=row['status'],
                last_tested_at=row['last_tested_at'].isoformat() if row['last_tested_at'] else None,
                last_error=row['last_error'],
                created_at=row['created_at'].isoformat() if row['created_at'] else None,
                updated_at=row['updated_at'].isoformat() if row['updated_at'] else None
            )
            for row in rows
        ]
    else:
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_custom_models 
                WHERE user_id = ? 
                AND assigned_roles_json IS NOT NULL
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
        
        result = []
        for row in rows:
            roles = _decode_json_field(row[8]) or []
            if role in roles:
                result.append(CustomModel(
                    id=row[0],
                    user_id=row[1],
                    name=row[2],
                    base_url=row[3],
                    model_id=row[4],
                    encrypted_api_key=row[5],
                    api_key_hint=row[6],
                    capabilities_json=json.loads(row[7]) if row[7] else None,
                    assigned_roles_json=roles,
                    default_model_id=row[9],
                    status=row[10],
                    last_tested_at=row[11],
                    last_error=row[12],
                    created_at=row[13],
                    updated_at=row[14]
                ))
        
        return result
