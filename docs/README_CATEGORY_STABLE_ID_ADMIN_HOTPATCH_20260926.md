# Category Stable-ID Administration Hot Patch — 2026-09-26

- Adds a stable `category_id` to category metadata without changing product IDs or deleting catalog data.
- Existing category metadata rows receive IDs during DB initialization; new categories receive an ID automatically.
- Category image replacement operates by stable ID and only updates the selected category image.
- Administrator rename operates by stable ID, supports case/name changes, and updates product category references.
- Rename is blocked if it would collide with another category.
- Administrator may delete unused/stale/duplicate categories with zero product references.
- Deletion is blocked when any Live, Coming Soon, or Archived catalog product references the category, and reports the reference count.
- Existing name-based endpoints/functions remain for compatibility; Administration UI uses the stable-ID endpoints.
- Manager deletion remains protected by the Administrator-only endpoint.
