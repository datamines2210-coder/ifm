# Manager Image Upload Permission Hot Patch — 2026-09-27

Root cause:
- Product image upload and the legacy category-image endpoint already accepted Administrator or Manager through `admin_required`.
- The newer stable-ID category image endpoint introduced by the production category repair used `administrator_only`, causing Manager category image uploads to return `403 Administrator access required`.

Repair:
- Stable-ID category image upload now uses `admin_required`, matching the documented Manager privilege model.
- Product image upload remains Administrator-or-Manager.
- Category Merge and Delete remain Administrator-only.
- No destructive privilege is granted to Manager.
- No database/schema, storefront, Basket, Orders or payment changes.
