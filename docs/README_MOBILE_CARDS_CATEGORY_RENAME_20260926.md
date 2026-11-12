# Mobile Product Cards + Category Rename Hot Patch — 2026-09-26

- Mobile product cards use normal document flow: image, compact name, weight/price badges, then Add to basket.
- Secondary category/state and external-link text are hidden only on compact cards; Product Quick View remains unchanged.
- Two columns are retained on normal phones and one column is used below 340px.
- Extra safe-area spacing prevents the fixed bottom navigation from covering products.
- Administration > Catalog Categories explicitly supports category rename/edit. Renaming updates catalog product category references transactionally.
- Case-insensitive rename collisions are rejected instead of merging categories.
- Category deletion is administrator-only and blocked while any Live, Coming Soon, or Archived product references the category.
