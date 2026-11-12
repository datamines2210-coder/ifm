#!/usr/bin/env python
"""Safely restore the Scorer SQLite database.

Preferred:
  python scripts/recover_scorer_data.py --source-db X:\\backup\\scorer.db

Fallback for this production package:
  python scripts/recover_scorer_data.py --sql-export scripts/migration/output/scorer_data.sql

The existing target is backed up before replacement. SQL fallback deliberately
skips orphaned team_players rows when their parent teams/players are absent.
"""
from __future__ import annotations
import argparse, os, re, shutil, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "scorer_data" / "scorer.db"
CORE_TABLES = ("players","matches","games","match_player_stats","point_events")
CHECK_TABLES = ("players","teams","team_players","matches","games","match_player_stats",
                "point_events","scorer_sessions","scorer_auth_logs","album")

def counts(path: Path):
    out={}
    with sqlite3.connect(path) as c:
        names={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
        for t in CHECK_TABLES:
            out[t]=c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] if t in names else None
    return out

def integrity(path: Path):
    with sqlite3.connect(path) as c:
        return c.execute("PRAGMA integrity_check").fetchone()[0]

def backup_target(target: Path):
    if not target.exists(): return None
    stamp=time.strftime("%Y%m%d-%H%M%S")
    b=target.with_name(f"{target.stem}.pre-recovery-{stamp}{target.suffix}")
    shutil.copy2(target,b)
    return b

def validate_source(path: Path):
    if not path.is_file(): raise SystemExit(f"Source database not found: {path}")
    if integrity(path)!="ok": raise SystemExit("Source SQLite integrity_check failed.")
    c=counts(path)
    missing=[t for t in CORE_TABLES if c.get(t) is None]
    if missing: raise SystemExit("Source is not a Scorer DB; missing tables: "+", ".join(missing))
    if not c.get("players"): raise SystemExit("Source Scorer DB contains no players.")
    return c

def init_empty(target: Path):
    target.parent.mkdir(parents=True,exist_ok=True)
    os.environ["SCORER_DB_PATH"]=str(target)
    sys.path.insert(0,str(ROOT))
    from app.scorer.database import init_db
    init_db()

def sql_statements(text):
    # Export contains MySQL FK toggles; INSERT syntax/backticks are SQLite compatible.
    text=re.sub(r"(?m)^SET FOREIGN_KEY_CHECKS=[01];\s*$","",text)
    buf=""
    for line in text.splitlines():
        if line.lstrip().startswith("--"): continue
        buf += line+"\n"
        if line.rstrip().endswith(";"):
            yield buf.strip()
            buf=""
    if buf.strip(): yield buf.strip()

def recover_from_sql(sql_path: Path, staged: Path):
    if not sql_path.is_file(): raise SystemExit(f"SQL export not found: {sql_path}")
    init_empty(staged)
    skipped=[]
    statements=list(sql_statements(sql_path.read_text(encoding="utf-8")))
    with sqlite3.connect(staged) as c:
        # The planning export is table-ordered rather than FK-ordered, so import
        # with FK checks disabled and validate the final state afterwards.
        c.execute("PRAGMA foreign_keys=OFF")
        # init_db may seed the administrator. Clear only tables actually present
        # in the export before replaying it, leaving newer configuration tables intact.
        exported=[]
        for stmt in statements:
            m=re.search(r"INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?",stmt,re.I)
            if m and m.group(1) not in exported: exported.append(m.group(1))
        for table in exported:
            c.execute(f'DELETE FROM "{table}"')
        for stmt in statements:
            c.execute(stmt)
        # The supplied export has team_players rows without exported parent
        # teams/players. Remove only those orphan mappings; preserve valid rows.
        before=c.execute("SELECT COUNT(*) FROM team_players").fetchone()[0]
        c.execute("""DELETE FROM team_players
                     WHERE team_id NOT IN (SELECT id FROM teams)
                        OR player_id NOT IN (SELECT id FROM players)""")
        after=c.execute("SELECT COUNT(*) FROM team_players").fetchone()[0]
        skipped.extend(["orphan"]*(before-after))
        c.commit()
        violations=c.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise SystemExit(f"Recovered SQL has unresolved foreign-key violations: {violations[:10]}")
    return len(skipped)

def install(staged: Path, target: Path):
    if integrity(staged)!="ok": raise SystemExit("Recovered database failed integrity_check.")
    new_counts=counts(staged)
    if not new_counts.get("players"): raise SystemExit("Recovered database has no players; refusing install.")
    target.parent.mkdir(parents=True,exist_ok=True)
    b=backup_target(target)
    os.replace(staged,target)
    return b,new_counts

def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--source-db",type=Path,help="Actual GoDaddy scorer.db (preferred)")
    g.add_argument("--sql-export",type=Path,help="Fallback scorer_data.sql export")
    p.add_argument("--target",type=Path,default=DEFAULT_TARGET)
    a=p.parse_args()
    target=a.target.resolve()
    staged=target.with_name(target.name+".recovery-staged")
    staged.unlink(missing_ok=True)
    if a.source_db:
        source=a.source_db.resolve()
        source_counts=validate_source(source)
        shutil.copy2(source,staged)
        skipped=0
        print("Validated source DB:", source)
        print("Source counts:", source_counts)
    else:
        skipped=recover_from_sql(a.sql_export.resolve(),staged)
        print("Recovered from SQL export:", a.sql_export.resolve())
        if skipped:
            print(f"Skipped {skipped} orphaned team_players INSERT statement(s); parent data was absent.")
    backup,new_counts=install(staged,target)
    print("Installed Scorer DB:",target)
    if backup: print("Previous DB backup:",backup)
    print("Recovered counts:",new_counts)
    print("SQLite integrity_check: ok")
    print("Restart the FastAPI application and sign in again; old session tokens may not be reusable.")

if __name__=="__main__":
    main()
