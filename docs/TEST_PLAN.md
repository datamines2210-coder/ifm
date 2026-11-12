# Test Plan v2

## Automated tests
- Health and readiness.
- Catalog search and category/state filtering.
- Customer signup.
- Customer login.
- Authenticated `/api/auth/me`.
- Checkout amount calculation from server-side catalog.
- Invalid product rejection.
- Razorpay HMAC signature verification.
- Request ID/security middleware.
- Metrics endpoint.

Run:

```powershell
python -m pytest -q
```

## Manual acceptance tests
1. Create a customer account.
2. Log out/clear local storage and log in again.
3. Search products and filter by category/state.
4. Add multiple quantities to basket.
5. Confirm total is calculated server-side.
6. Configure Razorpay Test Mode keys.
7. Complete a Razorpay test payment.
8. Confirm `/api/payments/verify` is called and order status becomes `paid`.
9. Try a modified/invalid signature and confirm payment is rejected.
10. Confirm health/readiness endpoints work.

## Production test gates
- Razorpay Test Mode end-to-end payment.
- Webhook verification and replay/idempotency tests.
- Password brute-force/rate-limit tests.
- CSRF/session policy review if browser cookies are introduced.
- PostgreSQL migration/integration tests.
- Load testing of catalog/search/checkout.
- Backup/restore test.
- Observability alert test.
