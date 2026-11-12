# Admin table pagination re-apply — 2026-09-21

Validated against the user-supplied 20260921-181638 project.

The previous patch only implemented paging for Session/Login History and Active Sessions. This re-apply adds real 25-row client-side pagination to Catalog Products, Catalog Categories, Orders, Customers/User Management, Offers, and Support/Customer Feedback while preserving the existing Session/Login History and Active Sessions pagination.

Search/category/status/stale filters are applied before pagination. Each pager shows the displayed range, total matching rows, current page/total pages, Previous and Next.

Validation: full pytest suite 130 passed.
