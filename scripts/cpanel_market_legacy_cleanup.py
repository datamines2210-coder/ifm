#!/usr/bin/env python3
"""Inventory and safely quarantine legacy service artifacts in Market production.

Dry-run is the default. Only exact, reviewed inventory paths can be quarantined.
The core application tree, runtime data, secrets, and Passenger configuration
are protected. Only app/scorer*, app/travel, app/sports, and app/community
service subtrees are eligible inside app/. Permanent deletion is separate.
"""
import argparse
import datetime
import json
import os
import pathlib
import shutil
import sys

SERVICE_NAMES = ("scorer2", "scorer", "travel", "sports", "community")
APP_SERVICE_DIRS = ("scorer", "scorer2", "travel", "sports", "community")
PROTECTED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "app", "uploads", "data", "logs", "backups",
    "backup", "releases", "release", "dist", "build", "docs", "tests",
}
PROTECTED_FILES = {
    "passenger_wsgi.py", "passenger.conf", "wsgi.py", ".htaccess",
    "requirements.txt", "pyproject.toml", "indian_family_market.db", "market.db",
    "database.sqlite", "database.sqlite3",
}
PROTECTED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".sql", ".pem", ".key", ".p12", ".pfx",
}
QUARANTINE_PREFIX = "indian-family-market_service_cleanup_quarantine_"
MARKER_NAME = ".service-cleanup-quarantine.json"


def has_service_name(path):
    name = path.name.lower()
    return any(service in name for service in SERVICE_NAMES)


def protected_path(relative, allow_app_service=False):
    parts = relative.parts
    if not parts:
        return True
    start = 0
    if allow_app_service and len(parts) >= 2 and parts[0] == "app" and parts[1] in APP_SERVICE_DIRS:
        start = 1
    for part in parts[start:]:
        lower = part.lower()
        suffix = pathlib.Path(lower).suffix
        if (allow_app_service and lower in {
                "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "tests"}):
            continue
        if (lower in PROTECTED_DIRS or lower.endswith("_data")
                or lower.endswith(("_album", "_photos", "_uploads"))
                or "upload" in lower
                or lower in PROTECTED_FILES or suffix in PROTECTED_SUFFIXES):
            return True
        if ".env" in lower or any(marker in lower for marker in ("backup", "recover", "restore")):
            return True
    return False


def raise_walk_error(error):
    raise error


def safe_tree(path, root, allow_app_service=False):
    """Reject symlinks and any candidate containing protected paths."""
    relative = path.relative_to(root)
    if path.is_symlink() or protected_path(relative, allow_app_service):
        return False
    if not path.is_dir():
        return path.is_file()
    for current, dirs, files in os.walk(path, followlinks=False, onerror=raise_walk_error):
        current_path = pathlib.Path(current)
        relative_current = current_path.relative_to(root)
        if protected_path(relative_current, allow_app_service):
            return False
        for name in dirs + files:
            child = current_path / name
            child_relative = child.relative_to(root)
            if child.is_symlink() or protected_path(child_relative, allow_app_service):
                return False
    return True


def find_candidates(root):
    """Find service-named files/trees, pruning protected and already-matched trees."""
    found = []
    for current, dirs, files in os.walk(
            root, topdown=True, followlinks=False, onerror=raise_walk_error):
        directory = pathlib.Path(current)
        relative_dir = directory.relative_to(root)
        dirs[:] = sorted(
            name for name in dirs
            if not (directory / name).is_symlink()
            and not protected_path(relative_dir / name)
        )
        if directory != root and has_service_name(directory):
            if safe_tree(directory, root):
                found.append(directory.relative_to(root).as_posix())
            dirs[:] = []
            continue
        for name in sorted(files):
            path = directory / name
            if has_service_name(path) and safe_tree(path, root):
                found.append(path.relative_to(root).as_posix())
    # Keep the application tree protected except for these retired service-owned
    # subtrees. Their sibling core modules remain outside cleanup scope.
    app_dir = root / "app"
    if app_dir.is_dir() and not app_dir.is_symlink():
        for name in APP_SERVICE_DIRS:
            path = app_dir / name
            if path.exists() and safe_tree(path, root, allow_app_service=True):
                found.append(path.relative_to(root).as_posix())
    return sorted(set(found))


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
    if any("\\" in item or "\x00" in item for item in paths):
        raise ValueError("Manifest paths must use safe, relative POSIX paths.")
    selected = set(paths)
    unknown = selected - set(candidates)
    if unknown:
        raise ValueError("Manifest paths are not eligible inventory candidates: "
                         + ", ".join(sorted(unknown)))
    for item in paths:
        parts = pathlib.PurePosixPath(item).parts
        if (not parts or pathlib.PurePosixPath(item).is_absolute()
                or any(part in ("", ".", "..") for part in parts)):
            raise ValueError(f"Unsafe manifest path: {item}")
    for item in selected:
        if any(other.startswith(item.rstrip("/") + "/") for other in selected if other != item):
            raise ValueError("Manifest must not include both a directory and its descendants.")
    return sorted(selected)


def quarantine_path(root):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return root.parent / f"{QUARANTINE_PREFIX}{stamp}"


def is_app_service_path(item):
    parts = pathlib.PurePosixPath(item).parts
    return len(parts) == 2 and parts[0] == "app" and parts[1] in APP_SERVICE_DIRS


def move_to_quarantine(root, selected, quarantine):
    if (quarantine == root or root in quarantine.parents
            or quarantine.parent != root.parent
            or not quarantine.name.startswith(QUARANTINE_PREFIX)):
        raise ValueError("Quarantine must be a named sibling of the application root.")
    for item in selected:
        source = root.joinpath(*pathlib.PurePosixPath(item).parts)
        if not source.exists() or not safe_tree(
                source, root, allow_app_service=is_app_service_path(item)):
            raise RuntimeError(f"Candidate changed or is no longer safe: {item}")
    quarantine.mkdir(parents=True, exist_ok=False)
    marker = {"application_root": str(root), "created_at": datetime.datetime.now().isoformat()}
    (quarantine / MARKER_NAME).write_text(json.dumps(marker, indent=2), encoding="utf-8")
    moved = 0
    for item in selected:
        source = root.joinpath(*pathlib.PurePosixPath(item).parts)
        if not source.exists() or not safe_tree(
                source, root, allow_app_service=is_app_service_path(item)):
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
    try:
        marker = json.loads((quarantine / MARKER_NAME).read_text(encoding="utf-8"))
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Absolute path to the Market application root")
    parser.add_argument("--manifest", help="JSON file listing exact reviewed inventory paths")
    parser.add_argument("--quarantine", action="store_true", help="Move approved paths outside the app root")
    parser.add_argument("--purge-quarantine", help="Permanently delete a verified quarantine directory")
    args = parser.parse_args(argv)

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

    try:
        candidates = find_candidates(root)
    except OSError as exc:
        print(f"ERROR: unable to complete inventory: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("Application root:", root)
    if not args.manifest:
        if args.quarantine:
            parser.error("--quarantine requires --manifest")
        print("Mode: DRY RUN (inventory only)")
        print("Review-required legacy service paths (not confirmed unused):")
        for item in candidates:
            print(" -", item)
        print("\nProtected: core app/ files, databases, .env files, uploads, Passenger configuration,")
        print("backups/recovery tools, docs/tests, virtual environments, and other core/runtime directories.")
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
