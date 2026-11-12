# Catalog category, import integrity and offer recommendations — 2026-09-21

- New product categories automatically appear in Admin category management and storefront category navigation.
- Category management now supports display name/rename, description, visibility, sort order, image, create and protected delete.
- Renaming a category updates its catalog products. Categories with live products cannot be deleted.
- Excel template columns are schema-driven from `CatalogItem`; newly added product-form/model fields are automatically included.
- Administrators can configure template column order; required import fields cannot be removed.
- Import is two-stage: validate/dry-run first, show new/update counts and errors, explicit confirmation, then one atomic database transaction. Invalid rows, duplicate IDs, invalid status, blank required values and MRP below selling price block the whole import.
- Missing spreadsheet rows are never deleted.
- Offers now displays explainable heuristic recommendations based on recent stored order history and current catalog pricing. It does not claim predictive accuracy and does not auto-activate offers.
- Existing database files are not replaced. Schema changes are additive.
- Validation: 130 tests passed.
