#!/usr/bin/env python3
"""Safely inventory and quarantine reviewed, non-runtime scorer/travel artifacts.

The default action is inventory only. Cleanup requires an exact JSON manifest and
moves selected paths to a sibling quarantine; it never edits application code.
"""
import argparse
import datetime
import json
import pathlib
import shutil
import sys

SERVICE_WORDS = ("scorer", "travel")
PROTECTED_TOP = {
    ".git", ".venv", "venv", "node_modules", "app", "static", "templates",
    "public", "data", "uploads", "logs", "backups", "backup", "releases",
    "release", "dist", "build", "artifacts",
}
PROTECTED_NAMES = {
    "passenger_wsgi.py", "requirements.txt", "indian_family_market.db",
    "market.db", "database.sqlite", "scorer.db", "travel.db",
}
PROTECTED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx"}
QUARANTINE_PREFIX = "indian-family-market_service_cleanup_quarantine_"
MARKER_NAME = ".service-cleanup-quarantine.json"


def has_service_name(path):
    return any(word in path.name.lower() for word in SERVICE_WORDS)


def protected_path(relative):
    parts = relative.parts
    if not parts or parts[0] in PROTECTED_TOP:
        return True
    for part in parts:
        lower = part.lower()
        if (lower in PROTECTED_NAMES or lower in {"scorer_data", "travel_data"}
                or lower.startswith(".env") or pathlib.Path(lower).suffix in PROTECTED_SUFFIXES):
            return True
    return False


def safe_tree(path, root):
    """Reject symlinks and protected content, including inside candidate folders."""
    relative = path.relative_to(root)
    if protected_path(relative) or path.is_symlink():
        return False
    if path.is_dir():
        for child in path.rglob("*"):
            child_relative = child.relative_to(root)
            if child.is_symlink() or protected_path(child_relative):
                return False
    return True


def find_candidates(root):
    """Return exact top-level and scripts/ service-named paths eligible for review."""
    found = set()
    search_roots = [root, root / "scripts"]
    for directory in search_roots:
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            children = directory.iterdir()
            for path in children:
                if path.name == "scripts" and directory == root:
                    continue
                relative = path.relative_to(root)
                if has_service_name(path) and safe_tree(path, root):
                    found.add(relative.as_posix())
        except OSError as exc:
            raise RuntimeError(f"Unable to inventory {directory}: {exc}") from exc
    return sorted(found)


def load_manifest(manifest_path, candidates):
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read manifest: {exc}") from exc
    paths = document.get("paths") if isinstance(document, dict) else None
    if not isinstance(paths, list) or not paths or not all(isinstance(item, str) for item in paths):
        raise ValueError('Manifest must be JSON with a non-empty "paths" string array.')
    if len(set(paths)) != len(paths):
        raise ValueError("Manifest contains duplicate paths.")
    selected = set(paths)
    unknown = selected - set(candidates)
    if unknown:
        raise ValueError("Manifest paths are not eligible inventory candidates: "
                         + ", ".join(sorted(unknown)))
    for item in paths:
        parts = pathlib.PurePosixPath(item).parts
        if not parts or pathlib.PurePosixPath(item).is_absolute() or ".." in parts:
            raise ValueError(f"Unsafe manifest path: {item}")
    # Moving a parent and one of its children in the same operation is ambiguous.
    for item in selected:
        if any(other.startswith(item.rstrip("/") + "/") for other in selected if other != item):
            raise ValueError("Manifest must not include both a directory and its descendants.")
    return sorted(selected)


def quarantine_path(root):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return root.parent / f"{QUARANTINE_PREFIX}{stamp}"


def move_to_quarantine(root, selected, quarantine):
    if (quarantine == root or root in quarantine.parents
            or quarantine.parent != root.parent
            or not quarantine.name.startswith(QUARANTINE_PREFIX)):
        raise ValueError("Quarantine must be a named sibling of the application root.")
    for item in selected:
        source = root.joinpath(*pathlib.PurePosixPath(item).parts)
        if not source.exists() or not safe_tree(source, root):
            raise RuntimeError(f"Candidate changed or is no longer safe: {item}")
    quarantine.mkdir(parents=True, exist_ok=False)
    marker = {"application_root": str(root), "created_at": datetime.datetime.now().isoformat()}
    (quarantine / MARKER_NAME).write_text(json.dumps(marker, indent=2), encoding="utf-8")
    moved = 0
    for item in selected:
        source = root.joinpath(*pathlib.PurePosixPath(item).parts)
        if not source.exists() or not safe_tree(source, root):
            raise RuntimeError(f"Candidate changed or is no longer safe: {item}")
        destination = quarantine.joinpath(*pathlib.PurePosixPath(item).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved += 1
    return moved


def purge_quarantine(root, quarantine):
    if (quarantine.is_symlink() or not quarantine.is_dir()
            or quarantine.parent != root.parent
            or not quarantine.name.startswith(QUARANTINE_PREFIX)):
        raise ValueError("Purge is limited to this tool's sibling quarantine directory.")
    marker_path = quarantine / MARKER_NAME
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Quarantine marker is missing or invalid; refusing purge.") from exc
    recorded_root = marker.get("application_root") if isinstance(marker, dict) else None
    if not isinstance(recorded_root, str) or pathlib.Path(recorded_root).resolve() != root:
        raise ValueError("Quarantine marker belongs to a different application root.")
    if input(f"Type PURGE to permanently delete {quarantine}: ") != "PURGE":
        print("Cancelled.")
        return False
    shutil.rmtree(quarantine)
    print("Quarantine permanently deleted.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Absolute path to the Market application root")
    parser.add_argument("--manifest", help='Reviewed JSON file, e.g. {"paths":["old-scorer-release"]}')
    parser.add_argument("--quarantine", action="store_true", help="Move manifest paths outside the app root")
    parser.add_argument("--purge-quarantine", help="Permanently delete a verified quarantine directory")
    args = parser.parse_args()

    root = pathlib.Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error("application root does not exist")
    if args.purge_quarantine:
        if args.manifest or args.quarantine:
            parser.error("--purge-quarantine cannot be combined with --manifest or --quarantine")
        try:
            purge_quarantine(root, pathlib.Path(args.purge_quarantine).expanduser().resolve())
        except ValueError as exc:
            parser.error(str(exc))
        return

    candidates = find_candidates(root)
    print("Application root:", root)
    if not args.manifest:
        if args.quarantine:
            parser.error("--quarantine requires --manifest")
        print("Mode: INVENTORY ONLY")
        print("Review-required service-named paths (not confirmed unused):")
        for item in candidates:
            print(" -", item)
        print("\nApplication source/runtime folders and sensitive data are excluded.")
        print("No files changed.")
        return

    try:
        selected = load_manifest(pathlib.Path(args.manifest).expanduser(), candidates)
    except ValueError as exc:
        parser.error(str(exc))

    print("Mode:", "QUARANTINE" if args.quarantine else "PLAN")
    print("Reviewed manifest paths:", len(selected))
    for item in selected:
        print(" -", item)
    if not args.quarantine:
        print("\nPlan only. No files changed.")
        return

    quarantine = quarantine_path(root)
    if input(f"Type QUARANTINE to move selected paths to {quarantine}: ") != "QUARANTINE":
        print("Cancelled.")
        return
    try:
        moved = move_to_quarantine(root, selected, quarantine)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: quarantine incomplete: {exc}", file=sys.stderr)
        print("Check the quarantine directory and restore any moved paths before retrying.",
              file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Moved {moved} reviewed paths to: {quarantine}")


if __name__ == "__main__":
    main()
