# Manual bulk user selection fix — 2026-09-21

## Fix
- The Select column now shows a checkbox for every account that is safe for bulk deletion, rather than only accounts already old enough for the stale threshold.
- Safe means: not the built-in administrator, not an admin/manager, and no order history.
- With Activity filter = Any activity, explicitly checked accounts can be manually bulk deleted even when recently active.
- With an inactivity filter selected (30/90/180/365 days), the server still enforces that stale threshold.
- Privileged accounts and accounts with order history remain protected server-side.

## Validation
- Focused admin/customer tests: 9 passed.
- Complete suite: 124 passed.
