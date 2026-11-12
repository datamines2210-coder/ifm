"""Heuristic SQLite -> MySQL column type mapping for migration planning.

SQLite has dynamic typing (type affinity only), so this mapping is a
best-effort default that a human must review before running any real DDL
against MySQL (see the "-- REVIEW" markers emitted by generate_mysql_schema.py).
"""
from __future__ import annotations

# Column names that should map to MySQL TEXT/LONGTEXT rather than VARCHAR(255),
# because they hold free-form or JSON content in the current SQLite schemas.
LONG_TEXT_COLUMNS = {
    "description", "notes", "caption", "details", "items_json", "value",
    "razorpay_checkout_url", "upi_redirect_url",
}

# Column names that hold a 0/1 flag in SQLite and should become MySQL TINYINT(1).
BOOLEAN_COLUMNS = {
    "active", "blocked", "must_change_password", "manual_override", "success",
}

# Column names that hold currency amounts and should become fixed-point DECIMAL,
# never floating point, to avoid rounding drift in MySQL.
MONEY_COLUMNS = {"price", "mrp", "amount"}

# Column names that are unix epoch seconds today; kept as BIGINT (not MySQL
# TIMESTAMP) so behavior matches the existing int(time.time()) app code exactly.
EPOCH_COLUMNS = {
    "created_at", "updated_at", "started_at", "ended_at", "expires_at",
    "occurred_at", "last_activity_at", "logged_out_at",
}


def map_column_type(column_name: str, sqlite_decl_type: str, is_primary_key: bool) -> tuple[str, str | None]:
    """Return (mysql_type, review_comment_or_None)."""
    decl = (sqlite_decl_type or "").upper()
    name = column_name.lower()

    if name in EPOCH_COLUMNS:
        return "BIGINT", None

    if name in BOOLEAN_COLUMNS:
        return "TINYINT(1)", None

    if name in MONEY_COLUMNS:
        return "DECIMAL(12,2)", "confirm currency precision/scale is sufficient"

    if "INT" in decl:
        return "BIGINT", None

    if decl in ("REAL", "DOUBLE", "FLOAT", "NUMERIC"):
        return "DOUBLE", None

    if decl in ("TEXT", "CLOB", "") or "CHAR" in decl:
        if is_primary_key or name.endswith("_id") or name == "id":
            return "VARCHAR(64)", None
        if name in LONG_TEXT_COLUMNS:
            return "TEXT", None
        return "VARCHAR(255)", "confirm 255 chars is enough for this column's real-world values"

    if decl == "BLOB":
        return "LONGBLOB", None

    return "VARCHAR(255)", f"unrecognized SQLite declared type '{sqlite_decl_type}', verify manually"
