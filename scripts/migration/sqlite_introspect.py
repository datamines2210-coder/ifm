"""Read-only SQLite schema introspection helpers for migration planning.

No writes, no MySQL connections. Only opens the given SQLite file in
read-only mode (via the "file:...?mode=ro" URI) so this tooling can never
accidentally modify a dev/prod SQLite file while planning the migration.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote


@dataclass
class ColumnInfo:
    cid: int
    name: str
    decl_type: str
    notnull: bool
    default: str | None
    pk: int  # 0 = not part of PK, >0 = position in composite PK


@dataclass
class ForeignKeyInfo:
    table: str
    from_col: str
    to_table: str
    to_col: str
    on_delete: str


@dataclass
class IndexInfo:
    name: str
    unique: bool
    columns: list[str]


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)
    row_count: int = 0


def connect_readonly(sqlite_path: Path) -> sqlite3.Connection:
    if not sqlite_path.exists():
        raise FileNotFoundError(
            f"SQLite file not found: {sqlite_path}. Run the app locally first so init_db() creates it, "
            "or point MIGRATION_*_SQLITE_PATH at the correct dev database."
        )
    uri = f"file:{quote(sqlite_path.as_posix(), safe='/:')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def introspect_table(conn: sqlite3.Connection, table: str, count_rows: bool = True) -> TableInfo:
    info = TableInfo(name=table)

    for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall():
        info.columns.append(
            ColumnInfo(
                cid=row["cid"],
                name=row["name"],
                decl_type=(row["type"] or "").upper(),
                notnull=bool(row["notnull"]),
                default=row["dflt_value"],
                pk=row["pk"],
            )
        )

    for row in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
        info.foreign_keys.append(
            ForeignKeyInfo(
                table=table,
                from_col=row["from"],
                to_table=row["table"],
                to_col=row["to"],
                on_delete=row["on_delete"] or "NO ACTION",
            )
        )

    for idx_row in conn.execute(f'PRAGMA index_list("{table}")').fetchall():
        idx_name = idx_row["name"]
        cols = [
            r["name"]
            for r in conn.execute(f'PRAGMA index_info("{idx_name}")').fetchall()
            if r["name"] is not None
        ]
        info.indexes.append(IndexInfo(name=idx_name, unique=bool(idx_row["unique"]), columns=cols))

    if count_rows:
        info.row_count = conn.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()["n"]

    return info


def introspect_database(sqlite_path: Path, count_rows: bool = True) -> list[TableInfo]:
    conn = connect_readonly(sqlite_path)
    try:
        return [introspect_table(conn, t, count_rows=count_rows) for t in list_tables(conn)]
    finally:
        conn.close()
