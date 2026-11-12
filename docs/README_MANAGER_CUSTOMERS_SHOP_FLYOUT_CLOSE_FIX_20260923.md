# Manager customers, Shop by category, and close-control fix — 2026-09-23

Baseline: `indian-family-market-production-20260923-020911.zip`.

- Manager/Staff Customers remains read-only and the Administrator password form is hidden for Manager sessions.
- Shop by category now opens a centered responsive fly-window. The previous markup nested the panel inside `.modal`, whose default CSS is `display:none`, preventing the panel from appearing even when its overlay opened.
- Storefront `.close` buttons suppress legacy literal `x` text and render exactly one `×` through `.close:before`.
- Basket behavior is unchanged.
