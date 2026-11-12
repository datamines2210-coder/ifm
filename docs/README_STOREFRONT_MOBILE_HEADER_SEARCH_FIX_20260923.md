# Storefront mobile header and search fix — 2026-09-23

Baseline: indian-family-market-production-20260922-181059.zip

- Restores product/category search using form submit, Enter, and debounced typing.
- Keeps Delivering to visible on mobile between search and account/basket actions.
- Keeps the basket control a fixed 54x54 square with rounded corners.
- Keeps the compact Login / Sign up account control.
- Synchronizes the mobile delivery-location label with the saved PIN/locality.
- No database, authentication, payment, basket API, or location API changes.
