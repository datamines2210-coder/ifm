# Account categories + administrator profile management — 2026-09-21

Implemented in Admin > Customers:
- Categories: Customers, Administrators, Managers / Staff, Test / System, All Accounts, each with live counts.
- Built-in administrator is shown as a protected Administrator record.
- Built-in administrator name, username, email and 10-digit phone can be edited from Details / Edit.
- Built-in administrator password can be reset from the same Customers management table; it cannot be deleted or demoted.
- Customer/manager/admin database accounts retain Details/Edit, password reset, role management and eligible deletion.
- Existing obvious automated-test accounts are categorized as Test / System rather than mixed into Customers.
- Storefront account dropdown editing controls are shown only to role=customer. Admin/manager storefront login exposes Administration + Logout only.
- Administrator login by username/email reads the persisted administrator profile, so updated administrator identity is used on subsequent logins.

Database migration is additive: admin_credentials gains name/email/username/phone columns when missing. Existing password and Market customer data are preserved.

Validation: 120 tests passed.
