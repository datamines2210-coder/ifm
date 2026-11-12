"""Service registry shared by the migration planning/readiness tools.

This module only describes *where the existing SQLite databases live* for
each independent service. It does not connect to MySQL and does not modify
any database. It mirrors the env vars already used by the running app
(see app/config.py and app/scorer/database.py) plus the MySQL target names
proposed in docs/DATABASE_DESIGN_MYSQL.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ServiceDb:
    name: str                 # logical service name, e.g. "market"
    sqlite_path: Path         # current SQLite source-of-truth file (dev)
    mysql_db_prod: str        # target MySQL database name (logical, before cPanel prefix)
    mysql_db_dev: str
    notes: str = ""


def _sqlite_market_path() -> Path:
    # Matches app/db.py db_path() default: sqlite:///./indian_family_market.db
    return Path(os.getenv("MIGRATION_MARKET_SQLITE_PATH", REPO_ROOT / "indian_family_market.db")).resolve()


def _sqlite_scorer_path() -> Path:
    # Matches app/scorer/database.py DB_PATH default: scorer_data/scorer.db
    return Path(os.getenv("MIGRATION_SCORER_SQLITE_PATH", REPO_ROOT / "scorer_data" / "scorer.db")).resolve()


SERVICES: dict[str, ServiceDb] = {
    "market": ServiceDb(
        name="market",
        sqlite_path=_sqlite_market_path(),
        mysql_db_prod="ifm_market_prod",
        mysql_db_dev="ifm_market_dev",
        notes="Main storefront: users, orders, payments, catalog, site_content.",
    ),
    "scorer": ServiceDb(
        name="scorer",
        sqlite_path=_sqlite_scorer_path(),
        mysql_db_prod="ifm_scorer_prod",
        mysql_db_dev="ifm_scorer_dev",
        notes="Badminton scorer: players, matches, games, point_events, stats, sessions.",
    ),
    # Travel and Sports currently ship with no database (static content).
    # Add entries here the day either service gains its own SQLite DB,
    # following the same one-service-one-file pattern.
}


def get_service(name: str) -> ServiceDb:
    try:
        return SERVICES[name]
    except KeyError as exc:
        available = ", ".join(sorted(SERVICES))
        raise SystemExit(f"Unknown service '{name}'. Available: {available}") from exc
