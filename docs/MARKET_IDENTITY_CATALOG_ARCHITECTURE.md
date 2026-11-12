# Market identity, catalog and service-isolation implementation

## Main storefront boundary
The Market runtime is the owner of Market customers, administrators, sessions, catalog, orders, payments, delivery, support and storefront content. Travel, Sports and Scorer remain available alongside Market in the same FastAPI deployment, but each service owns its own database and identity/session boundary.

`app/main.py` mounts each extended service through an isolation wrapper. Import or database-initialization failure in one optional service is logged as degraded and does not prevent Market from starting. Healthy extended services remain mounted at `/travel`, `/sports`, `/scorer` and their own `/api/<service>` namespaces. Market does not reuse their users, sessions, roles or business tables, and they do not reuse Market identity data.

## Unified identity
The storefront uses one login endpoint for customer, manager and administrator identities. Login accepts username or email address. A successful administrator/manager login redirects the browser to `/admin` using the same bearer token/session. Customer sessions remain separate rows in `auth_sessions`; an administrator can inspect and revoke one session without terminating unrelated sessions.

Customer-editable data is intentionally limited to account identity/contact fields, password, and address. Order/payment/delivery/support statuses, catalog, pricing, offers, roles and bank information are server-authoritative/admin-controlled. Bank data exposed to customers is read-only and should be stored only when the business has a real requirement; prefer payment-provider tokens/references and masked account values rather than raw account/card credentials.

## SQLite to MySQL compatibility
This change follows the existing phased migration plan in `MYSQL_MIGRATION_STRATEGY.md`: SQLite remains the current source of truth and no production MySQL cutover is performed by this patch. New `customer_profiles` data is owned by the Market database only. Before MySQL cutover, include it in the reviewed Market DDL/export/readiness tooling and validate it during the dev rehearsal. The runtime DB adapter should be converted during the planned Phase 4 dialect work rather than introducing an unreviewed dual-write path.

## Catalog/storage strategy
Use the relational database for product metadata and state: SKU/product ID, title, category, region, unit, price/MRP, availability, offer rules, image references, timestamps and status. Store product images as objects/files outside the relational database and persist only durable image URLs/keys. Do not store large base64 images in catalog rows.

For bulk catalog management, use an administrator-only CSV/XLSX import workflow with a staging/validation step: validate required columns, duplicate SKU, decimal price, category/state vocabulary and image references; show a dry-run summary; then commit the accepted batch in one transaction and write an audit record. Use soft archive/versioning rather than destructive product deletion. For mobile, serve responsive WebP/AVIF thumbnails, lazy-load below-the-fold images, paginate/filter server-side, and keep product payloads small.

As the catalog grows, separate inventory/stock movements from the product master and keep price/offer history in append-only history tables. Search can start with indexed MySQL fields and move to a dedicated search service only when scale/quality justifies it.
