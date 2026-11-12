# Storefront mobile header and close controls hot patch — 2026-09-22

Baseline: `indian-family-market-production-20260922-181059.zip`.

Changes are limited to `static/index.html` and do not change Market authentication, database, basket, or map APIs.

- Restores a visible X close control for Login / Sign up, Basket, and Choose delivery location.
- Uses a compact round account control on mobile.
- Uses a compact square basket control with quantity badge on mobile.
- Keeps Delivering to visible and centered in the mobile header.
- Synchronizes the mobile delivery label with the selected PIN/locality.
- Desktop layout remains responsive and retains the existing delivery location in the sub-navigation.
