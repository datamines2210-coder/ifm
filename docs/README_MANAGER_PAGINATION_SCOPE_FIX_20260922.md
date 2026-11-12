# Manager pagination scope fix — 2026-09-22

Fixes the Manager / Staff Admin UI regression where Catalog Categories, Orders, Offers and Support displayed `pageRows is not defined`.

Root cause: the validated 25-row pagination helpers and backing arrays were scoped inside one JavaScript IIFE, while the later Manager-role render overrides were installed from a separate IIFE and could not access them.

Changes:
- Expose the shared pagination helpers and category/order/feedback backing arrays at page scope for the role-aware renderers.
- Override the actual Catalog `render()` function for Manager/Staff so product Delete/Archive remains hidden while Add/Edit/Image remain available.
- Preserve 25-row pagination for Administrator and Manager/Staff views.
- No database schema or data changes.
