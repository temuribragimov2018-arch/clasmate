"""Добавляет недостающие колонки (Railway / локально). create_all таблицы не ALTER'ит."""
import logging
from sqlalchemy import text, inspect
from backend.database import engine

logger = logging.getLogger("classmate.migrate")

NEW_COLUMNS = {
    "users": [
        ("device_type", "VARCHAR(20) DEFAULT 'phone'"),
        ("social_bonus_claimed", "BOOLEAN DEFAULT FALSE"),
        ("social_modal_seen", "BOOLEAN DEFAULT FALSE"),
        ("coin_balance", "INTEGER DEFAULT 0"),
        ("coin_purchased", "INTEGER DEFAULT 0"),
        ("followers_count", "INTEGER DEFAULT 0"),
        ("following_count", "INTEGER DEFAULT 0"),
        ("posts_count", "INTEGER DEFAULT 0"),
        ("monetization_enabled", "BOOLEAN DEFAULT FALSE"),
    ],
    "payments": [
        ("payment_method", "VARCHAR(20) DEFAULT 'screenshot'"),
        ("payer_phone", "VARCHAR(50)"),
        ("payment_date", "VARCHAR(50)"),
        ("manual_note", "TEXT"),
    ],
    "homeworks": [
        ("file_url", "VARCHAR(500)"),
    ],
}


def ensure_schema() -> dict:
    """
    Добавляет недостающие колонки. Безопасно вызывать при каждом старте.
    Возвращает сводку: {"added": [...], "skipped": [...], "errors": [...]}
    """
    summary = {"added": [], "skipped": [], "errors": [], "tables_missing": []}
    logger.info("Migration started (dialect=%s)", engine.dialect.name)

    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        logger.info("Found tables: %s", sorted(tables) if tables else "(none)")
    except Exception as e:
        logger.exception("Cannot list tables: %s", e)
        summary["errors"].append(f"list_tables: {e}")
        return summary

    dialect = engine.dialect.name
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if table not in tables:
                logger.warning("Table %s missing — create_all should create it", table)
                summary["tables_missing"].append(table)
                continue
            try:
                existing = {c["name"] for c in insp.get_columns(table)}
                logger.debug("Table %s existing columns: %s", table, sorted(existing))
            except Exception as e:
                logger.warning("Cannot inspect columns of %s: %s", table, e)
                existing = set()

            for col_name, col_type in cols:
                if col_name in existing:
                    summary["skipped"].append(f"{table}.{col_name}")
                    logger.debug("Skip existing column %s.%s", table, col_name)
                    continue
                try:
                    if dialect == "postgresql":
                        sql = f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}'
                    else:
                        sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    logger.info("Executing: %s", sql)
                    conn.execute(text(sql))
                    summary["added"].append(f"{table}.{col_name}")
                    logger.info("Added column %s.%s (%s)", table, col_name, col_type)
                except Exception as e:
                    msg = str(e).lower()
                    if "already exists" in msg or "duplicate" in msg:
                        summary["skipped"].append(f"{table}.{col_name}")
                        logger.info("Column %s.%s already exists", table, col_name)
                    else:
                        summary["errors"].append(f"{table}.{col_name}: {e}")
                        logger.error("Failed to add %s.%s: %s", table, col_name, e)

    logger.info(
        "Migration finished: added=%d skipped=%d errors=%d missing_tables=%d",
        len(summary["added"]),
        len(summary["skipped"]),
        len(summary["errors"]),
        len(summary["tables_missing"]),
    )
    if summary["added"]:
        logger.info("Columns added: %s", ", ".join(summary["added"]))
    if summary["errors"]:
        logger.error("Migration errors: %s", "; ".join(summary["errors"]))
    return summary


def fix_chat_type_column():
    """Convert chats.chat_type from PG ENUM to VARCHAR so 'staff' works."""
    dialect = engine.dialect.name
    logger = __import__("logging").getLogger("classmate.migrate")
    if dialect != "postgresql":
        return {"ok": True, "note": "not postgresql"}
    try:
        with engine.begin() as conn:
            # Add staff to enum if still enum, OR convert to varchar
            try:
                conn.execute(text(
                    "ALTER TABLE chats ALTER COLUMN chat_type TYPE VARCHAR(20) USING chat_type::text"
                ))
                logger.info("chats.chat_type converted to VARCHAR(20)")
            except Exception as e:
                logger.warning("chat_type alter: %s", e)
                try:
                    conn.execute(text("ALTER TYPE chattype ADD VALUE IF NOT EXISTS 'staff'"))
                    logger.info("Added staff to chattype enum")
                except Exception as e2:
                    logger.warning("enum add staff: %s", e2)
        return {"ok": True}
    except Exception as e:
        logger.exception("fix_chat_type_column: %s", e)
        return {"ok": False, "error": str(e)}


def force_user_columns() -> dict:
    """Принудительно добавить критичные колонки users (PostgreSQL IF NOT EXISTS)."""
    summary = {"added": [], "errors": []}
    cols = [
        ("coin_balance", "INTEGER DEFAULT 0"),
        ("coin_purchased", "INTEGER DEFAULT 0"),
        ("followers_count", "INTEGER DEFAULT 0"),
        ("following_count", "INTEGER DEFAULT 0"),
        ("posts_count", "INTEGER DEFAULT 0"),
        ("monetization_enabled", "BOOLEAN DEFAULT FALSE"),
    ]
    dialect = engine.dialect.name
    logger.info("Force user columns (dialect=%s)", dialect)
    try:
        with engine.begin() as conn:
            for col_name, col_type in cols:
                try:
                    if dialect == "postgresql":
                        sql = f'ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}'
                    else:
                        sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"
                    logger.info("Force SQL: %s", sql)
                    conn.execute(text(sql))
                    summary["added"].append(col_name)
                    logger.info("Forced column users.%s", col_name)
                except Exception as e:
                    summary["errors"].append(f"{col_name}: {e}")
                    logger.warning("Force col %s: %s", col_name, e)
    except Exception as e:
        logger.exception("Force migrate failed: %s", e)
        summary["errors"].append(str(e))
    return summary
