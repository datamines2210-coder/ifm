# Admin table pagination audit — 2026-09-21

Reviewed every Admin tab from Catalog through Sessions & Logs.

Tables now use 25 rows per page with Previous/Next controls:
- Catalog products
- Catalog categories
- Orders
- Customers / user management
- Offers
- Support / customer feedback
- Session / login history (already implemented; preserved)
- Active customer sessions (already implemented; preserved)

Homepage and Payments currently contain configuration/forms rather than tabular datasets, so no pagination was added there.

Filtering/searching is applied before pagination where applicable. Existing Sessions & Logs pagination was left intact as requested.
