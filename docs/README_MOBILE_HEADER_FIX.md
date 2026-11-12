# Mobile header fix — 2026-09-20

Fixes the storefront mobile header distortion reported on narrow Android/Chrome screens.

Root cause: the <=620px CSS declared three grid columns but the search row declared four grid-area cells (`search search search search`). CSS Grid therefore created an implicit fourth column, pushing/clipping the brand, account, basket and search controls.

Changes:
- Search row now spans exactly the three declared mobile columns.
- Account and Basket are explicitly right-aligned.
- Search input can shrink correctly while the search button keeps a fixed width.
- Brand and announcement text receive narrow-screen overflow guards.
- No authentication, database, Travel, Sports or Scorer logic changed.

Validation: `PYTHONPATH=. pytest -q` => 108 passed.
