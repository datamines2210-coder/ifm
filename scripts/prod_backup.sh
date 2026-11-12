#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   APP_ROOT=/home/CPANELUSER/indian-family-market ./scripts/prod_backup.sh
# Optional:
#   BACKUP_ROOT=/home/CPANELUSER/ifm-backups RETENTION_DAYS=30 PYTHON_BIN=/path/to/python

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BACKUP_ROOT="${BACKUP_ROOT:-$APP_ROOT/backups/database}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STAMP="$(date '+%Y%m%d-%H%M%S')"
DEST="$BACKUP_ROOT/$STAMP"

mkdir -p "$DEST"

APP_ROOT="$APP_ROOT" DEST="$DEST" "$PYTHON_BIN" - <<'PY'
import os, sqlite3
from pathlib import Path

root = Path(os.environ['APP_ROOT']).resolve()
dest = Path(os.environ['DEST']).resolve()

databases = {
    'indian_family_market.db': root / 'indian_family_market.db',
    'scorer.db': root / 'scorer_data' / 'scorer.db',
    'travel.db': root / 'travel_data' / 'travel.db',
    'sports.db': root / 'sports_data' / 'sports.db',
}

for name, source in databases.items():
    if not source.exists():
        print(f'SKIP {source} (not present)')
        continue
    target = dest / name
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
        check = dst.execute('PRAGMA integrity_check').fetchone()[0]
        if check != 'ok':
            raise SystemExit(f'Integrity check failed for {target}: {check}')
    print(f'BACKUP {source} -> {target}')
PY

cat > "$DEST/manifest.txt" <<EOF_MANIFEST
created_at=$STAMP
app_root=$APP_ROOT
retention_days=$RETENTION_DAYS
EOF_MANIFEST

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -print -exec rm -rf {} \;

echo "Production database backup complete: $DEST"
