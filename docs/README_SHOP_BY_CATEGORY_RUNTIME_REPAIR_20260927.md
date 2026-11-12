# Shop by Category Runtime Repair — 2026-09-27

Root cause: the previous responsive-selection patch introduced a JavaScript parse error in the generated Browse fallback markup. Because that script block failed to parse, unrelated storefront handlers in the same block—including account and Shop by category interactions—did not initialize.

Repair:
- Corrected the malformed nested string/template expression.
- Preserved category click → filter → close behavior.
- Preserved active-category highlighting and responsive mobile selector.
- Added a regression test that runs `node --check` against every inline script block so a future UI patch cannot silently ship with the same parse failure.
- No database, authentication backend, Basket, catalog data, or payment changes.
