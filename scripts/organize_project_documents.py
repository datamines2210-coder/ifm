#!/usr/bin/env python
"""Move project documentation artifacts into docs/.

Only files outside docs/ are moved. Code, ZIPs, databases, HTML, JSON, CSV,
images and runtime data are not touched.

Usage:
    python scripts/organize_project_documents.py
    python scripts/organize_project_documents.py --dry-run
"""
from __future__ import annotations
import argparse, shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from document_paths import DOCUMENT_EXTENSIONS, docs_root

ROOT=Path(__file__).resolve().parents[1]
SKIP_DIRS={".git",".venv","venv","env","node_modules","__pycache__",".pytest_cache","docs"}

def unique_destination(dst: Path) -> Path:
    if not dst.exists(): return dst
    stem,suffix=dst.stem,dst.suffix
    n=2
    while True:
        candidate=dst.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists(): return candidate
        n+=1

def candidates(root: Path):
    docs=(root/"docs").resolve()
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in DOCUMENT_EXTENSIONS: continue
        try: rel=p.relative_to(root)
        except ValueError: continue
        if any(part in SKIP_DIRS for part in rel.parts[:-1]): continue
        if docs in p.resolve().parents: continue
        yield p

def organize(root: Path=ROOT,dry_run: bool=False):
    target=docs_root(root)
    moved=[]
    for src in list(candidates(root)):
        dst=unique_destination(target/src.name)
        moved.append((src,dst))
        print(f"{'WOULD MOVE' if dry_run else 'MOVE'}: {src.relative_to(root)} -> {dst.relative_to(root)}")
        if not dry_run:
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(src),str(dst))
    print(f"{len(moved)} document file(s) {'identified' if dry_run else 'moved'} into docs/.")
    return moved

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    organize(ROOT,args.dry_run)
