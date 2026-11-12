# Catalog search and administrator multi-select hot patch — 2026-09-24

This patch moves the Catalog product search/filter toolbar below **Bulk catalog refresh** and adds Administrator-only product multi-selection.

## Product review workflow

The Catalog API annotates products from the most recent template validation report as `valid`, `stale` (missing from the latest validated template), or `validation_error`. Administrators can filter these states, select products on the visible page, and archive or permanently delete the selected records.

Managers keep their existing Catalog add/edit access but do not receive selection, bulk archive, or bulk delete controls. Both bulk endpoints enforce `administrator_only` server-side.

## Safety

Archive is reversible at the catalog-record level and removes the selected product from the active storefront. Permanent delete is all-or-nothing when order history is involved: if any selected product is referenced in an order's saved `items_json`, deletion is rejected and the administrator is told to archive instead. Managed product image files are removed after a successful permanent deletion; external image URLs are never deleted.

Template refresh continues not to delete missing spreadsheet rows automatically. Stale products are surfaced for administrator review instead.
