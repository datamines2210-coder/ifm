# Storefront Mobile Header Consolidated Fix — 2026-09-23

Baseline: `indian-family-market-production-20260923-013634.zip`.

This hot patch consolidates the storefront mobile-header fixes against the supplied current production build.

- Keeps storefront search functional for typing, Enter/submit, and the search button.
- Keeps the mobile Delivering-to control visible in the mobile header and hides the duplicate sub-navigation location control on mobile.
- Keeps the Basket control at the established compact 64px × 56px dimensions and uses the explicit `basket-icon` element.
- Keeps the compact account control and explicit `account-icon` / Login-Sign up label hooks.
- Keeps visible × close controls for Login/Signup, Basket, and delivery-location overlays.
- Synchronizes the selected delivery locality/PIN to the mobile location label.
- Does not change backend APIs, authentication, database, payments, or Scorer.

Validation: full pytest suite: 135 passed, 0 failed.
