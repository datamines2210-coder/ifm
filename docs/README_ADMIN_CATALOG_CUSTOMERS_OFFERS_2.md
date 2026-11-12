# Market Admin Catalog / Customers / Offers update — 2026-09-20

Implemented against `indian-family-market-production-20260920-095127.zip`.

## Catalog
- Added `Coming Soon` product status (stored as `coming_soon`). Existing DBs receive the new `catalog.status` column automatically.
- Corrected the Admin image save flow so the selected image is uploaded before the editor closes/reloads. Managed images remain under `static/uploads/catalog`; the DB stores only the URL/path.
- Added XLSX/CSV catalog refresh. Download the current catalog as an XLSX template. Existing stable product IDs update; new IDs insert; rows absent from the spreadsheet are not deleted. Invalid rows reject the entire import before writes.

## Customers
- Replaced the loose customer list with a table.
- Admin can add and edit customer/account/address/admin-managed bank metadata.
- Admin can delete customers only when there is no order history. Customers with order history are protected from hard deletion for audit/data integrity.

## Offers
- Added a dedicated Offers tab and `offers` table.
- Supports title, slogan, description, type/value, code, scope/target, image, CTA, placement, status and priority.
- Active offers are exposed at `/api/offers` and can replace storefront offer cards / hero copy.
- Model is intentionally relational and MySQL-portable; marketing integrations can use stable offer IDs/API later.

## Dependencies
- Added `openpyxl==3.1.5` for Excel import/export.

## Validation
- Full suite: 110 passed.
- Admin/storefront JavaScript syntax checked with Node.
- Travel, Sports and Scorer code/database boundaries were not changed.
