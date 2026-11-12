"""Readiness checks for the SQLite -> MySQL migration (planning only).

Runs read-only checks against a service's existing SQLite database and
reports issues that would block or complicate a MySQL migration, e.g.:
- Duplicate values in columns that must be UNIQUE in MySQL.
- NULLs in columns the SQLite schema declares NOT NULL (already enforced by
  SQLite, but re-checked to catch legacy rows written before NOT NULL was added).
- Oversized text values relative to the draft VARCHAR(255) mapping.
- Orphaned foreign keys (rows referencing a parent id that no longer exists).

Nothing here writes to SQLite or connects to MySQL. Output is a plain-text
report intended to be attached to the migration Go/No-Go review.

Usage:
    python scripts/migration/verify_readiness.py market
    python scripts/migration/verify_readiness.py scorer --out scripts/migration/output
"""
from __future__ import annotations

import argparse
from pathlib import Path

from config import get_service
from sqlite_introspect import connect_readonly, introspect_database

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "output"
VARCHAR_DEFAULT_LEN = 255


def check_duplicates(conn, table_name: str, unique_indexes) -> list[str]:
    issues = []
    for idx in unique_indexes:
        cols = ", ".join(f'"{c}"' for c in idx.columns)
        query = (
            f'SELECT {cols}, COUNT(*) AS n FROM "{table_name}" '
            f'GROUP BY {cols} HAVING COUNT(*) > 1'
        )
        rows = conn.execute(query).fetchall()
        if rows:
            issues.append(
                f"[{table_name}] unique index '{idx.name}' on ({', '.join(idx.columns)}) "
                f"has {len(rows)} duplicate group(s) that will violate a MySQL UNIQUE constraint."
            )
    return issues


def check_notnull_violations(conn, table_name: str, columns) -> list[str]:
    issues = []
    for col in columns:
        if not col.notnull:
            continue
        n = conn.execute(f'SELECT COUNT(*) AS n FROM "{table_name}" WHERE "{col.name}" IS NULL').fetchone()["n"]
        if n:
            issues.append(f"[{table_name}.{col.name}] {n} NULL row(s) in a NOT NULL column.")
    return issues


def check_oversized_text(conn, table_name: str, columns) -> list[str]:
    issues = []
    for col in columns:
        decl = (col.decl_type or "").upper()
        if "CHAR" in decl or decl in ("TEXT", "CLOB", ""):
            row = conn.execute(
                f'SELECT MAX(LENGTH("{col.name}")) AS n FROM "{table_name}"'
            ).fetchone()
            max_len = row["n"] or 0
            if max_len > VARCHAR_DEFAULT_LEN:
                issues.append(
                    f"[{table_name}.{col.name}] longest value is {max_len} chars, "
                    f"exceeds the draft VARCHAR({VARCHAR_DEFAULT_LEN}) mapping — use TEXT or a wider VARCHAR."
                )
    return issues


def check_orphaned_foreign_keys(conn, table_name: str, foreign_keys) -> list[str]:
    issues = []
    for fk in foreign_keys:
        query = (
            f'SELECT COUNT(*) AS n FROM "{table_name}" t '
            f'WHERE t."{fk.from_col}" IS NOT NULL '
            f'AND NOT EXISTS (SELECT 1 FROM "{fk.to_table}" p WHERE p."{fk.to_col}" = t."{fk.from_col}")'
        )
        n = conn.execute(query).fetchone()["n"]
        if n:
            issues.append(
                f"[{table_name}.{fk.from_col}] {n} row(s) reference a missing "
                f"'{fk.to_table}.{fk.to_col}' — would violate a MySQL FOREIGN KEY constraint."
            )
    return issues


def run_readiness_check(service_name: str) -> tuple[list[str], list[str]]:
    service = get_service(service_name)
    conn = connect_readonly(service.sqlite_path)
    tables = introspect_database(service.sqlite_path, count_rows=True)

    all_issues: list[str] = []
    summary: list[str] = [f"Readiness check for service '{service_name}' ({service.sqlite_path})"]
    try:
        for table in tables:
            summary.append(f"  table {table.name}: {table.row_count} rows")
            unique_indexes = [i for i in table.indexes if i.unique]
            all_issues += check_duplicates(conn, table.name, unique_indexes)
            all_issues += check_notnull_violations(conn, table.name, table.columns)
            all_issues += check_oversized_text(conn, table.name, table.columns)
            all_issues += check_orphaned_foreign_keys(conn, table.name, table.foreign_keys)
    finally:
        conn.close()

    return summary, all_issues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", help="Service name, e.g. market or scorer")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for the report")
    args = parser.parse_args()

    summary, issues = run_readiness_check(args.service)

    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"{args.service}_readiness_report.txt"

    lines = list(summary)
    lines.append("")
    if issues:
        lines.append(f"BLOCKING/REVIEW ITEMS ({len(issues)}):")
        lines.extend(f"  - {i}" for i in issues)
        lines.append("")
        lines.append("Resolve or explicitly accept every item above before scheduling a migration cutover.")
    else:
        lines.append("No blocking items found by this automated check.")
        lines.append("Manual review of the strategy checklist in docs/MYSQL_MIGRATION_STRATEGY.md is still required.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nReport written to {report_path}")
    print("This tool made no changes to SQLite or MySQL.")


if __name__ == "__main__":
    main()
