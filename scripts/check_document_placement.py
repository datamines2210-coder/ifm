#!/usr/bin/env python
"""CI/pre-deployment guard: fail if documentation files exist outside docs/."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from document_paths import DOCUMENT_EXTENSIONS

ROOT=Path(__file__).resolve().parents[1]
SKIP={".git",".venv","venv","env","node_modules","__pycache__",".pytest_cache","docs"}
bad=[]
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in DOCUMENT_EXTENSIONS: continue
    rel=p.relative_to(ROOT)
    if any(part in SKIP for part in rel.parts[:-1]): continue
    bad.append(rel)
if bad:
    print("Documentation files outside docs/:")
    for p in bad: print(" -",p)
    raise SystemExit(1)
print("Document placement policy: PASS")
