# Storefront search, Shop by category, and Manager customer view

- Search now matches product name, description, state, category, and unit. Enter/search button scrolls to results.
- Removed the word Account from the logged-out Login / Sign up control.
- Shop by category opens a responsive fly window sourced from active catalog categories/products. Category display names/descriptions/images remain customizable under Admin > Catalog; the fly-window title can use Homepage panel key `shop_by_category`.
- Manager storefront account menu exposes Change password.
- Manager Admin console exposes Customers as a server-filtered, read-only customer-only list. Administrator, manager/staff, and test/system accounts are not returned to manager sessions; edit/delete/reset/role actions remain administrator-only.
