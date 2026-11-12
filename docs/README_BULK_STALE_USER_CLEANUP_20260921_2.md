# Admin Customers — bulk stale-user cleanup

Adds safe bulk cleanup under Admin > Customers.

- Activity filter: Any, Never used, inactive 30/90/180/365+ days.
- Optional "No orders only" view filter.
- Select eligible accounts currently shown and delete them in one confirmed action.
- Server re-validates every selected account before deletion.
- Built-in administrator, admin/manager accounts, accounts with order history, and accounts newer/more active than the selected cutoff are protected/skipped.
- Shows last activity and order count in the customer table.
- Default deletion cutoff is 90 days when the UI is on Any/Never-used mode.
- No database schema migration is required.

Validation: 122 tests passed.
