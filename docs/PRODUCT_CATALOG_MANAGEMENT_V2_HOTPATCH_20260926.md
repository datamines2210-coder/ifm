# Product & Catalog Management v2 Hot Patch — 2026-09-26

## Implemented
- Existing product image mapping is preserved when Excel image is blank.
- Download/snapshots are regenerated from current DB state for round-trip image integrity.
- Import modes: update existing; Administrator-only authoritative rebuild (missing rows archived, stable IDs retained).
- Single daily snapshot plus separate pre-operation safety snapshots.
- Backup/Restore history moved to a separate paginated UI; Templates remains a compact summary.
- Catalog import concurrency lock.
- On-demand deterministic image recovery scan and Administrator exact-ID remap.
- Stable category IDs, rename, duplicate merge, protected delete and Administrator force cleanup.
- Force cleanup creates a pre-operation snapshot and supports reassign, archive/rehome, or delete-products strategies.

## Compatibility
- No customer/Basket/payment schema changes.
- Existing Market catalog/storefront APIs remain in place.
- Physical images remain outside the DB under static/uploads/catalog.
- No runtime DB or uploaded image files are included in this hot patch.
- New logic is structured to preserve stable IDs for later SQLite → MySQL migration.
