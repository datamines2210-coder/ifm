# Market test-contract update — 2026-09-21

This patch updates legacy automated tests to the current Market identity contract.

Production behavior is intentionally unchanged:
- username remains mandatory for customer/admin-created accounts;
- login continues to support username or email plus password;
- customer Bank Details remain editable per the latest requirement.

Updated tests now supply unique usernames for signup/admin-user creation and validate customer bank-detail editing rather than the superseded read-only rule.

Validation: 116 passed, 0 failed.
