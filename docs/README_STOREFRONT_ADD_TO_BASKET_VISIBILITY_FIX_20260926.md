# Storefront Add to Basket Visibility Hot Patch — 2026-09-26

## Fix
Product-card purchase controls now use a reserved bottom action zone. Image-backed cards can no longer push the `Add to basket` control outside the visible card body.

- Live products: `Add to basket` and quick-add `+` remain visible.
- Coming Soon products: the same action zone shows disabled `Coming Soon`.
- Mobile cards reserve equivalent space for the action zone.
- No payment, authentication, database, catalog status, or Scorer logic is changed by this incremental patch.

## Validation
Focused storefront tests: 8 passed.
Full suite: 183 passed, 0 failed, 1 pre-existing Scorer fixture setup error (`client` fixture missing for `test_generate_preview_distributes_single_coach`).
