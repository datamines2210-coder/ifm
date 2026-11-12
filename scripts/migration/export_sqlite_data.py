"""Export SQLite table data as batched MySQL-compatible INSERT statements.

PLANNING/READINESS TOOL — this only *writes .sql files to disk*. It never
opens a MySQL connection and never imports anything anywhere. Running this
script against dev is safe (read-only against SQLite); it is the artifact a
human/DBA will later choose to run against a MySQL dev database as part of
the actual migration (a separate, deliberate step — see the strategy doc).

Usage:
    python scripts/migration/export_sqlite_data.py market
    python scripts/migration/export_sqlite_data.py scorer --batch-size 500
"""
from __future__ import annotations

import argparse
from pathlib import Path

from config import get_service
from sqlite_introspect import connect_readonly, introspect_database

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "output"


def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        return "0x" + value.hex()
    text = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{text}'"


def export_table(conn, table_name: str, columns, batch_size: int) -> list[str]:
    col_names = [c.name for c in columns]
    col_list = ", ".join(f"`{c}`" for c in col_names)
    statements: list[str] = []

    cursor = conn.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in col_names)} FROM "{table_name}"')
    batch: list[str] = []
    for row in cursor:
        values = ", ".join(sql_literal(row[c]) for c in col_names)
        batch.append(f"({values})")
        if len(batch) >= batch_size:
            statements.append(f"INSERT INTO `{table_name}` ({col_list}) VALUES\n" + ",\n".join(batch) + ";")
            batch = []
    if batch:
        statements.append(f"INSERT INTO `{table_name}` ({col_list}) VALUES\n" + ",\n".join(batch) + ";")

    return statements


def export_service(service_name: str, out_dir: Path, batch_size: int) -> Path:
    service = get_service(service_name)
    tables = introspect_database(service.sqlite_path, count_rows=True)
    conn = connect_readonly(service.sqlite_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{service_name}_data.sql"

    try:
        with out_file.open("w", encoding="utf-8") as fh:
            fh.write(f"-- Data export for service '{service_name}'\n")
            fh.write(f"-- Source: {service.sqlite_path}\n")
            fh.write("-- STATUS: planning artifact only. Not executed against MySQL by this script.\n")
            fh.write("SET FOREIGN_KEY_CHECKS=0;\n\n")
            for table in tables:
                fh.write(f"-- {table.name}: {table.row_count} row(s)\n")
                for stmt in export_table(conn, table.name, table.columns, batch_size):
                    fh.write(stmt + "\n\n")
            fh.write("SET FOREIGN_KEY_CHECKS=1;\n")
    finally:
        conn.close()

    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", help="Service name, e.g. market or scorer")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for the .sql file")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per multi-row INSERT statement")
    args = parser.parse_args()

    out_file = export_service(args.service, args.out, args.batch_size)
    print(f"Wrote data export: {out_file}")
    print("This tool made no changes to SQLite and did not connect to MySQL.")


if __name__ == "__main__":
    main()
