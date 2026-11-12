# Market single-session and role management — 2026-09-22

## Identity/session protection
- Market permits one active authenticated session per user identity across supported browsers/devices.
- A successful new login closes any previous active Market session for the same user.
- Changing a user's role closes that user's active session so the new authorization takes effect on the next login.
- This policy is limited to Market identity/session tables and does not couple Travel, Sports, or Scorer authentication.

## Roles
- Administrator: existing full administration, including user/role management and destructive actions.
- Customer: public signup always creates this role; no Market administration access.
- Manager / Staff (Power-user): Catalog create/edit/image upload; category create/edit/image upload; Orders read-only; Offers recommendations/view/create; Support view/status/respond. Destructive catalog/category actions, order updates, offer edit/delete, user/role management, payment/homepage/session administration are denied server-side.

## Support
- Feedback now supports an administrator/manager response field. Existing databases are upgraded additively with `feedback.admin_response`.

## Security
UI restrictions are convenience only. Authorization is enforced by FastAPI dependencies on each protected endpoint.
