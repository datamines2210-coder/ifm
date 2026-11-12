# Migration Planning Tools (SQLite → MySQL)

**Status: planning/readiness tooling only.** Nothing in this folder connects to MySQL or
executes a migration. Every script is read-only against the existing SQLite dev database and
only ever *writes plain `.sql`/`.txt` files* under `scripts/migration/output/` for a human to
review. See [docs/MYSQL_MIGRATION_STRATEGY.md](../../docs/MYSQL_MIGRATION_STRATEGY.md) for the
phased plan these tools support.

## Tools

| Script | Purpose | Reads | Writes |
|---|---|---|---|
| `config.py` | Service registry (SQLite path + target MySQL DB names) | — | — |
| `sqlite_introspect.py` | Shared read-only schema/row introspection helpers | SQLite (mode=ro) | — |
| `type_mapping.py` | Heuristic SQLite → MySQL column type mapping | — | — |
| `generate_mysql_schema.py` | Emits a draft `CREATE TABLE` script per service | SQLite (mode=ro) | `output/<service>_<env>_schema.sql` |
| `export_sqlite_data.py` | Emits batched MySQL `INSERT` statements per service | SQLite (mode=ro) | `output/<service>_data.sql` |
| `verify_readiness.py` | Flags duplicates/NULLs/oversized text/orphaned FKs that would break on MySQL | SQLite (mode=ro) | `output/<service>_readiness_report.txt` |

## Usage (safe to run any time against dev — read-only)

```bash
# 1) Readiness check first — fix data issues before generating anything else
python scripts/migration/verify_readiness.py market
python scripts/migration/verify_readiness.py scorer

# 2) Draft MySQL schema (review every "-- REVIEW" comment before trusting it)
python scripts/migration/generate_mysql_schema.py market --env dev
python scripts/migration/generate_mysql_schema.py scorer --env dev

# 3) Draft data export (do NOT run this against MySQL yet — see strategy doc phases)
python scripts/migration/export_sqlite_data.py market
python scripts/migration/export_sqlite_data.py scorer
```

All output lands in `scripts/migration/output/` (git-ignored — see `.gitignore`), so re-running
any tool is always safe and never silently commits generated SQL to the repo.

## Explicitly out of scope for these scripts

- Creating a MySQL database or user (see the `CREATE DATABASE`/`GRANT` examples in
  [docs/DATABASE_DESIGN_MYSQL.md](../../docs/DATABASE_DESIGN_MYSQL.md) — run manually, later).
- Running the generated schema/data `.sql` files against any MySQL server.
- Any prod database access — these tools only ever point at the local dev SQLite files.
