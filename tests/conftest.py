import os
import tempfile
import uuid
from pathlib import Path

# PID-based filenames can collide when the OS reuses process IDs across
# short-lived test runs, silently reusing a stale DB from an earlier run.
# A random suffix guarantees a fresh, isolated database every session.
_db_path = Path(tempfile.gettempdir()) / f"indian_family_scorer_{os.getpid()}_{uuid.uuid4().hex}.db"
_db_path.unlink(missing_ok=True)
os.environ["SCORER_DB_PATH"] = str(_db_path)

# Keep Market tests isolated from the developer/production SQLite database.
# app.config.Settings reads DATABASE_URL when app.main is imported below by tests.
_market_db_path = Path(tempfile.gettempdir()) / f"indian_family_market_{os.getpid()}_{uuid.uuid4().hex}.db"
_market_db_path.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_market_db_path}"

_travel_db_path = Path(tempfile.gettempdir()) / f"indian_family_travel_{os.getpid()}_{uuid.uuid4().hex}.db"
_travel_db_path.unlink(missing_ok=True)
os.environ["TRAVEL_DB_PATH"] = str(_travel_db_path)

_sports_db_path = Path(tempfile.gettempdir()) / f"indian_family_sports_{os.getpid()}_{uuid.uuid4().hex}.db"
_sports_db_path.unlink(missing_ok=True)
os.environ["SPORTS_DB_PATH"] = str(_sports_db_path)
