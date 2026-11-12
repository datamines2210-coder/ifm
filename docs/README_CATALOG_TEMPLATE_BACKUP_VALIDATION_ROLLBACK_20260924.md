# Catalog template validation, backup and rollback hot patch

- Supports slash-separated price/MRP/unit variants during validation (validated positionally). The current catalog schema continues to use the first variant as the operational price/unit until a full selectable-variant checkout model is introduced.
- Every confirmed Upload / Refresh creates a backup of the previously active template before the catalog transaction.
- Adds a Templates section at the top of Administrator > Catalog with last-validation errors and latest-vs-current comparison, authenticated downloads, deletion and rollback.
- Last validation can be downloaded as an HTML report.
- Active template is changed only after administrator confirmation and successful catalog database update.
- Backup/candidate templates are automatically retained for 30 days; manual cleanup supports older than 1/3/6/12 months and custom date ranges.
- Displays approximate used bytes for the Market SQLite database, catalog images and template storage.
- Rollback itself backs up the current active template first.

No SQLite database or catalog image is included in this patch.
