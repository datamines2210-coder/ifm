# Shop by category mega-menu position fix — 2026-09-23

Baseline: `indian-family-market-production-20260923-022650.zip`.

The mega-menu container was rendered after the footer. Its `position:absolute` therefore opened at the bottom of the document even though the navigation arrow changed state. The container is now placed immediately after the storefront sub-navigation, so the existing open/close logic displays the menu directly below `Shop by category`.

No catalog API, database, authentication, manager permissions, basket, payment, or scorer behavior is changed.
