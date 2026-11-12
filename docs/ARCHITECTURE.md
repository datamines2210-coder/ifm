# Indian Family Market — Architecture v2

## Goals
- BigBasket-inspired grocery discovery and basket experience without copying proprietary branding/UI.
- Customer accounts and authenticated checkout.
- Razorpay Standard Checkout with server-side order creation and signature verification.
- AU Small Finance Bank API Banking (Collection API) as an alternate, admin-selectable payment
  gateway — storefront-only, independent of the Travel/Sports services (see
  [app/payments/au_bank.py](../app/payments/au_bank.py)).
- Local development at `http://localhost:8020` and IDE-friendly workflows.
- Testable, observable FastAPI backend.

## Runtime

```text
Browser
  |
  | HTTPS / localhost
  v
FastAPI + Uvicorn (:8020)
  |-- /api/catalog
  |-- /api/auth/signup
  |-- /api/auth/login
  |-- /api/auth/me
  |-- /api/checkout
  |-- /api/payments/verify
  |-- /api/payments/au-bank/webhook
  |-- /api/orders/{id}
  |-- /api/health
  |-- /api/ready
  |-- /metrics
  |
  +--> SQLite (development) / PostgreSQL-ready boundary
  |
  +--> Razorpay Orders API + Standard Checkout
  |
  +--> AU Small Finance Bank API Banking (OAuth2 + Collection API)
  |
  +--> Alert webhook
```

## Authentication
Passwords are hashed with PBKDF2-HMAC-SHA256. The application issues a signed bearer token for the customer session. The signing secret is configured through `AUTH_SECRET` and must be replaced with a long random secret outside development.

## Payment flow
1. Browser submits cart and delivery details to `/api/checkout`.
2. Server recalculates all prices from the server catalog; the browser never determines the payable amount.
3. Server creates a Razorpay Order when live/test keys are configured.
4. Browser opens Razorpay Standard Checkout using the returned `order_id` and public key ID.
5. Razorpay returns payment ID, order ID and signature to the browser.
6. Browser posts those fields to `/api/payments/verify`.
7. Server verifies the signature with the Razorpay secret and marks the order paid.
8. Production should also consume Razorpay webhooks and verify final payment/capture state before fulfilment.

Razorpay's current documentation requires an Order for each payment and server-side signature verification before fulfilment. See the official docs linked from `README.md`.

## AU Bank payment flow (alternate gateway)
Admins select the active gateway via `payment_settings.provider` (`razorpay` | `upi` | `au_bank`),
saved through `/api/admin/payment-settings` — no code change needed to switch.

1. `/api/checkout` calls `AUBankGateway.create_collection_order()` when `provider=au_bank`.
2. The gateway authenticates with AU Bank via OAuth2 client-credentials
   (`AU_BANK_CLIENT_ID`/`AU_BANK_CLIENT_SECRET`, cached until near expiry) and calls the
   Collection API to obtain a Dynamic QR / payment link for the order.
3. AU Bank confirms payment asynchronously via a signed callback to
   `/api/payments/au-bank/webhook` (HMAC-SHA256 over the raw body, `AU_BANK_WEBHOOK_SECRET`),
   which looks the order up by its stored gateway reference and marks it paid/failed.
4. Without `AU_BANK_CLIENT_ID`/`AU_BANK_CLIENT_SECRET`/`AU_BANK_MERCHANT_ID` configured, the
   gateway returns a `mock` order (same fallback pattern as Razorpay) so dev/test never needs
   live bank credentials.

Per AU Bank's API Banking onboarding (https://www.au.bank.in/business-banking/api-banking),
credentials and the exact Collection/Status endpoint contract are issued after signing the API
banking agreement; endpoint paths are configurable (`AU_BANK_*_PATH` in `.env`) so only
[app/payments/au_bank.py](../app/payments/au_bank.py) needs updating once the bank confirms the
final sandbox/live contract — the checkout flow itself never changes.

## Catalog
The current public parent site does not provide a dependable structured SKU feed in this starter. Demo products are therefore explicitly marked as demo data. The importer boundary should be replaced with an authorised CSV/JSON/API source before production commerce.

## Observability
- JSON application logs.
- Request IDs.
- `/api/health` for liveness.
- `/api/ready` for readiness.
- `/metrics` for a lightweight Prometheus-compatible counter surface.
- Alert webhook adapter.

## IDE
The `.vscode/` directory contains launch configurations and tasks for running Uvicorn and pytest. On Windows, `setup_vscode_and_run.bat` can install Visual Studio Code through `winget` if it is not already available, then open the project.
