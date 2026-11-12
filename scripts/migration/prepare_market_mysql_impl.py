"""Implementation for the Python-version-checking workflow launcher.

This workflow never connects to or writes to MySQL. It creates a consistent
SQLite snapshot, runs the app tests against an explicitly confirmed MySQL
development URL, then checks and exports data from the snapshot.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_ROOT = Path.home() / ".ifm-mysql-migration"
MIGRATION_DIR = Path(__file__).resolve().parent


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def confirm(prompt: str, expected: str) -> None:
    response = input(f"{prompt}\nType {expected!r} to continue: ").strip()
    if response != expected:
        raise RuntimeError("Confirmation did not match; stopping without proceeding.")


def ask_nonempty(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise RuntimeError("A required confirmation was not provided.")
    return value


def parse_mysql_target(database_url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(database_url)
        host = parsed.hostname or ""
    except ValueError as exc:
        raise RuntimeError("DATABASE_URL is not a valid MySQL URL.") from None
    if not (parsed.scheme == "mysql" or parsed.scheme.startswith("mysql+")):
        raise RuntimeError(
            "DATABASE_URL must use a MySQL driver URL (mysql:// or mysql+driver://) "
            "for the rehearsal."
        )
    database = unquote(parsed.path.lstrip("/"))
    if not host or not database or "/" in database:
        raise RuntimeError("DATABASE_URL must include a MySQL host and one database name.")
    production_marker = re.compile(r"(^|[_-])prod(uction)?($|[_-])", re.IGNORECASE)
    if production_marker.search(database) or production_marker.search(host):
        raise RuntimeError(
            "The rehearsal URL appears to name a production host or database; "
            "use a dedicated non-production MySQL database."
        )
    return host, database


def create_snapshot(source_path: Path, snapshot_path: Path) -> None:
    source_uri = f"file:{quote(source_path.as_posix(), safe='/:')}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        with closing(sqlite3.connect(snapshot_path)) as snapshot:
            source.backup(snapshot)
            result = snapshot.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                detail = result[0] if result else "no result"
                raise RuntimeError(f"SQLite snapshot integrity check failed: {detail}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def run_tool(script_name: str, snapshot_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MIGRATION_MARKET_SQLITE_PATH"] = str(snapshot_path)
    result = subprocess.run(
        [
            sys.executable,
            str(MIGRATION_DIR / script_name),
            "market",
            "--out",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"{script_name} failed with exit code {result.returncode}.")
    return result


def run_workflow(source: Path, work_root: Path) -> Path:
    source = source.expanduser().resolve(strict=True)
    work_root = work_root.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"SQLite source is not a file: {source}")
    if is_within(work_root, REPO_ROOT):
        raise RuntimeError(
            "Migration output must be outside the application repository because it contains "
            "customer data."
        )
    if source == work_root or is_within(work_root, source):
        raise RuntimeError("The migration output directory must not overwrite the source database.")

    confirm(
        "Confirm that this is the SQLite database used by the live cPanel Market app:\n"
        f"{source}",
        str(source),
    )
    account_backup_reference = ask_nonempty(
        "Enter the reference/location of the completed full cPanel account backup "
        "(this script cannot create or verify that account backup): "
    )
    confirm(
        "Confirm the separate full cPanel/app backup is complete and its restore procedure is known.",
        "BACKUP CONFIRMED",
    )

    work_root.mkdir(parents=True, exist_ok=True)
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = work_root / f"market-{run_name}"
    run_dir.mkdir(mode=0o700)
    if os.name != "nt":
        run_dir.chmod(0o700)

    snapshot_path = run_dir / "market-production-snapshot.sqlite3"
    manifest_path = run_dir / "manifest.json"
    manifest = {
        "service": "market",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sqlite": str(source),
        "account_backup_reference": account_backup_reference,
        "snapshot": str(snapshot_path),
        "stages": {
            "backup_and_confirm_source": "in_progress",
            "prepare_app_and_rehearse_off_production": "pending",
            "check_and_prepare_data": "pending",
        },
    }

    create_snapshot(source, snapshot_path)
    if os.name != "nt":
        snapshot_path.chmod(0o600)
    manifest["snapshot_sha256"] = sha256_file(snapshot_path)
    manifest["stages"]["backup_and_confirm_source"] = "complete"
    write_manifest(manifest_path, manifest)
    print(f"\nVerified SQLite snapshot: {snapshot_path}")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "Set DATABASE_URL to the dedicated MySQL development database before running "
            "the rehearsal; the application default is SQLite."
        )
    host, database = parse_mysql_target(database_url)
    print(f"\nStep 2 target (credentials hidden): host={host}, database={database}")
    confirm(
        "Confirm this is an isolated MySQL development/rehearsal database, not production, "
        "and that the app's MySQL driver/database layer changes are ready.",
        database,
    )
    confirm(
        "The next command runs the complete pytest suite with this DATABASE_URL. "
        "Confirm the tests may write to the named development database.",
        "RUN TESTS",
    )
    test_result = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        check=False,
    )
    manifest["rehearsal_test_exit_code"] = test_result.returncode
    if test_result.returncode:
        manifest["stages"]["prepare_app_and_rehearse_off_production"] = "failed"
        write_manifest(manifest_path, manifest)
        raise RuntimeError(
            f"The rehearsal test suite failed with exit code {test_result.returncode}; "
            f"see the test output. Manifest: {manifest_path}"
        )
    confirm(
        "Run the rehearsal app's manual key-flow checks (login, admin, checkout/payment "
        "callbacks, and routine writes). Confirm they all passed.",
        "SMOKE TESTS PASSED",
    )
    manifest["stages"]["prepare_app_and_rehearse_off_production"] = "complete"
    write_manifest(manifest_path, manifest)

    output_dir = run_dir / "review"
    output_dir.mkdir(mode=0o700)
    run_tool("verify_readiness.py", snapshot_path, output_dir)
    readiness_report = output_dir / "market_readiness_report.txt"
    report_text = readiness_report.read_text(encoding="utf-8")
    manifest["readiness_report"] = str(readiness_report)
    if "BLOCKING/REVIEW ITEMS (" in report_text:
        manifest["stages"]["check_and_prepare_data"] = "blocked_by_readiness_items"
        write_manifest(manifest_path, manifest)
        raise RuntimeError(
            "Readiness found data issues. Resolve them on a copy, then rerun this workflow. "
            f"Report: {readiness_report}"
        )

    run_tool("generate_mysql_schema.py", snapshot_path, output_dir)
    run_tool("export_sqlite_data.py", snapshot_path, output_dir)
    for generated_file in output_dir.iterdir():
        if generated_file.is_file() and os.name != "nt":
            generated_file.chmod(0o600)
    manifest["stages"]["check_and_prepare_data"] = "complete"
    manifest["review_files"] = [
        str(output_dir / "market_readiness_report.txt"),
        str(output_dir / "market_dev_schema.sql"),
        str(output_dir / "market_data.sql"),
    ]
    write_manifest(manifest_path, manifest)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Explicit path to the live cPanel Market SQLite database; never inferred.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=DEFAULT_WORK_ROOT,
        help=f"Private output root outside the repository (default: {DEFAULT_WORK_ROOT})",
    )
    args = parser.parse_args()
    run_dir = run_workflow(args.source, args.work_dir)
    print(f"\nAll three steps completed. Review the sensitive artifacts in: {run_dir}")
    print("No MySQL connection/import was performed. Do not use the draft SQL before review.")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, OSError, sqlite3.Error, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
