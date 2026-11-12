# Scorer Live Scoring Font Update — 2026-09-14

UI-only change to `static/scorer.html`.

Live scoring:
- Team A / Team B headings remain 15px.
- Player names changed to 14px.
- Service Fault / Service Return / Unforced Error / Forced Error buttons changed to 14px.
- Error counts remain without parentheses and changed to 14px bold.

No backend, database, statistics, ranking, authentication, or scoring logic was changed.

Apply by replacing the existing `static/scorer.html` in the current Indian Family Market v2 project. Backup the existing file first.

## Market standalone runtime (2026-09-19)
`app.main:app` is now the standalone Indian Family Market runtime. It does not import, initialize, or mount Travel, Sports, or Scorer. The storefront uses unified customer/administrator login through `/api/auth/login`, with username/email identity, persistent per-session records, customer profile/address management, and administrator-only control of critical commerce/session data. See `docs/MARKET_IDENTITY_CATALOG_ARCHITECTURE.md`.
