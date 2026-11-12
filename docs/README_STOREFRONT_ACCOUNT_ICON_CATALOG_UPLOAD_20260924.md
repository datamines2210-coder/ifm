# Storefront account icon and Catalog upload hot patch — 2026-09-24

## Changes
- Storefront account icon is now a dark-green inline SVG. Desktop remains 20 px; mobile (<=768 px) is 16 px.
- Administrator > Catalog renames `Import / refresh` to `Import` and adds `Upload / Refresh`.
- `Import` validates the selected XLSX/CSV without writing catalog data.
- `Upload / Refresh` validates first, asks for confirmation, then atomically inserts/updates catalog rows. Missing spreadsheet rows are not deleted.
- XLSX endpoints return a controlled service error if `openpyxl` is unavailable instead of exposing a raw module import exception.

## Production dependency
`requirements.txt` already pins `openpyxl==3.1.5`. On GoDaddy/cPanel, install/reinstall the project requirements in the active Python application environment and restart the application. Applying source files alone cannot install a Python package into an existing virtual environment.

## Validation
Targeted suite: 19 passed.
Full suite: 165 passed, 1 pre-existing Scorer test collection/setup error (`test_generate_preview_distributes_single_coach`: fixture `client` not found). No Market/storefront/catalog test failed.
