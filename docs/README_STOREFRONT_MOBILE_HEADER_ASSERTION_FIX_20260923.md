# Storefront mobile header assertion fix — 2026-09-23

Hot patch for the current storefront mobile header.

Changes:
- Restores the explicit `account-icon` element required by the storefront control contract.
- Keeps the account label and mobile-first account presentation.
- Sets the Basket mobile control to an explicit 64px × 56px compact rectangular/square-like control as required by the current responsive test contract.
- Preserves the search behavior, mobile Delivering-to placement, and explicit close controls from the preceding storefront patches.

No database, authentication API, payment, order, or scorer changes are included.
