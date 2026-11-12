# Indian Family: isolated packaging and hot patching

## Build scripts

- `python create_market_zip.py`: Market-only application. No scorer/travel/sports Python implementations. **Not a drop-in replacement for the currently combined GoDaddy site**: its service API routes require external routing. Landing pages remain, but API handlers are not present.
- `python create_scorer_package_zip.py`: standalone Scorer, including `expense_scheduler.py`.
- `python create_travel_package_zip.py`: standalone Travel.
- `python create_sports_package_zip.py`: standalone Sports.
- `python create_production_zip.py`: complete legacy Market + all three service implementations, retaining existing routes.

Build scripts produce sibling ZIP files, include SHA256 manifests, and omit runtime databases, uploads, secrets, caches, and previous ZIPs. All ZIPs use relative paths rooted at their application release.

## Deployment and patches

Each standalone application needs its **own cPanel Python application root, Python environment, database, secrets, persistent data directory, and Passenger restart**. For an isolated root, create `.application-id` containing exactly `market`, `scorer`, `travel`, or `sports`. Use `python apply_service_patch.py --package /path/to/scorer.zip --root /path/to/scorer --application scorer` only after backup and staging validation. The patch tool rejects mismatched application identities, checks hashes and backs up overwritten files in `_patch_backups/`. It does not run migrations, restart processes, delete old files, or automatically roll back after a failed write; those remain deployment-operator responsibilities.

**Never apply standalone service packages to the combined Market root**. Combined deployments must use the complete production ZIP and a coordinated restart. True independent hot patching requires the separate runtime instances and web-server path routing (or subdomains); packaging alone does not isolate processes. Check GoDaddy/cPanel support before cutover.

## Databases and engine scope

Only Market is approved for a future SQLite-to-MySQL migration; this patch performs **no migration**. Scorer, Travel and Sports retain their existing data stores. Scorer Players/Matches, Statistics and Expenses remain internal functional engines, not separately deployed applications. Engine refactoring is outside this packaging-only patch.

## Required release checks

1. Generate all five packages and inspect manifest file lists.
2. Ensure production package contains `app/main.py` and all three routers; standalone ZIPs do not contain any other service's Python code.
3. Validate Python compilation and startup using clean extracted directories and separate test databases.
4. Validate login, service API routes, static assets, expense scheduler configuration, and per-service database isolation.
5. Test a service-only patch and rollback in staging before changing GoDaddy production.
