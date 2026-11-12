# Administration KPI Regression Repair — 2026-09-27

Root cause: the later Manager Save permission hot patch carried an older `static/admin.html`, which overwrote the earlier Catalog KPI visibility correction when patches were applied sequentially.

This cumulative repair keeps BOTH changes:
- Catalog KPI cards are visible only while Catalog is the active Administration view.
- Orders, Customers, Offers, Support and other views hide Catalog KPI cards.
- Manager/Administrator product and category image/save permissions from the later patch remain intact.
- Category Save success confirmation remains intact.

Future hot patches should be built cumulatively from the latest patched baseline rather than replacing a shared file with an older copy.
