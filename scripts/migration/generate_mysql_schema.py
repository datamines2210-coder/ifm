"""Generate draft MySQL CREATE TABLE DDL from a service's existing SQLite schema.

PLANNING TOOL ONLY:
- Read-only against the SQLite source (opened via mode=ro).
- Never connects to MySQL and never executes anything against MySQL.
- Writes a .sql file for a human to review/edit before it is ever run.

Usage:
    python scripts/migration/generate_mysql_schema.py market --env dev
    python scripts/migration/generate_mysql_schema.py scorer --env dev --out scripts/migration/output
"""
from __future__ import annotations

import argparse
from pathlib import Path

from config import get_service
from sqlite_introspect import TableInfo, introspect_database
from type_mapping import map_column_type

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "output"


def render_table_ddl(table: TableInfo) -> str:
    lines: list[str] = []
    review: list[str] = []
    pk_cols = [c.name for c in sorted(table.columns, key=lambda c: c.pk) if c.pk > 0]

    lines.append(f"CREATE TABLE IF NOT EXISTS `{table.name}` (")
    col_defs = []
    for col in table.columns:
        mysql_type, note = map_column_type(col.name, col.decl_type, is_primary_key=col.name in pk_cols)
        if note:
            review.append(f"-- REVIEW [{table.name}.{col.name}]: {note}")
        parts = [f"  `{col.name}` {mysql_type}"]
        if col.notnull or col.pk > 0:
            parts.append("NOT NULL")
        if col.default is not None:
            parts.append(f"DEFAULT {col.default}")
        col_defs.append(" ".join(parts))

    if pk_cols:
        pk_list = ", ".join(f"`{c}`" for c in pk_cols)
        col_defs.append(f"  PRIMARY KEY ({pk_list})")

    for fk in table.foreign_keys:
        col_defs.append(
            f"  FOREIGN KEY (`{fk.from_col}`) REFERENCES `{fk.to_table}` (`{fk.to_col}`) "
            f"ON DELETE {fk.on_delete if fk.on_delete != 'NO ACTION' else 'RESTRICT'}"
        )

    lines.append(",\n".join(col_defs))
    lines.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;")

    index_lines = []
    for idx in table.indexes:
        if idx.unique and set(idx.columns) == set(pk_cols):
            continue  # already expressed as PRIMARY KEY
        kind = "UNIQUE INDEX" if idx.unique else "INDEX"
        cols = ", ".join(f"`{c}`" for c in idx.columns)
        index_lines.append(f"CREATE {kind} `{idx.name}` ON `{table.name}` ({cols});")

    out = "\n".join(lines)
    if index_lines:
        out += "\n" + "\n".join(index_lines)
    if review:
        out = "\n".join(review) + "\n" + out
    return out


def generate(service_name: str, env: str, out_dir: Path) -> Path:
    service = get_service(service_name)
    tables = introspect_database(service.sqlite_path, count_rows=True)

    mysql_db = service.mysql_db_prod if env == "prod" else service.mysql_db_dev
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{service_name}_{env}_schema.sql"

    header = (
        f"-- DRAFT MySQL schema for service '{service_name}' ({env})\n"
        f"-- Generated from SQLite source: {service.sqlite_path}\n"
        f"-- Target logical database (before cPanel prefix): {mysql_db}\n"
        "-- STATUS: planning artifact only. Review every '-- REVIEW' marker before use.\n"
        "-- This script performed NO writes to SQLite or MySQL.\n\n"
        f"-- CREATE DATABASE `{mysql_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
        f"-- USE `{mysql_db}`;\n\n"
    )

    body = "\n\n".join(render_table_ddl(t) for t in tables)
    summary = "\n".join(f"-- table {t.name}: {len(t.columns)} columns, {t.row_count} rows (dev snapshot)" for t in tables)

    out_file.write_text(header + summary + "\n\n" + body + "\n", encoding="utf-8")
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", help="Service name, e.g. market or scorer")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev",
                         help="Which target database name to reference in the header comment (schema shape is the same)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for the .sql file")
    args = parser.parse_args()

    out_file = generate(args.service, args.env, args.out)
    print(f"Wrote draft schema: {out_file}")
    print("This is a planning artifact. No database was created or modified.")


if __name__ == "__main__":
    main()
