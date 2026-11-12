# Admin sessions, category media, and map pinning — 2026-09-21

Implemented on the 2026-09-21 Market build.

- Admin > Sessions & Logs: both auth-log and session tables page at 25 rows; active sessions have an administrator-only Terminate session action.
- Admin > Catalog: category-picture manager supports JPEG/PNG/WebP/GIF/AVIF uploads under `static/uploads/categories`; category images are exposed to the storefront and used on category tiles.
- Storefront delivery location: interactive OpenStreetMap/Leaflet map, click-to-pin and browser current-location support; reverse lookup identifies locality/city/state/PIN.
- Customer > Address: saves address plus locality, latitude and longitude; map pinning can populate locality/city/state/PIN.
- SQLite migration is additive: `customer_profiles.locality`, `latitude`, `longitude` plus `catalog_category_media`.
- Reverse geocoding is proxied server-side with a named User-Agent, serialized to <= 1 request/sec and cached in memory. Map attribution remains visible.
- No existing database file is packaged or overwritten.

Validation: 127 tests passed.
