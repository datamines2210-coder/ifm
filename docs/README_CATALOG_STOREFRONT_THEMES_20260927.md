# Catalog Storefront Themes Hot Patch — 2026-09-27

Baseline: `indian-family-market-production-20260927-152707.zip`.

Administration > Catalog > Catalog Items View / Layout provides three responsive storefront themes:

- Modern Market (default): balanced image-first category and product cards.
- Premium Showcase: larger photography, editorial spacing and premium presentation.
- Compact Grocery: denser high-volume browsing with more items visible.

Administrator can select, preview, and Save & Publish. Manager can view/select for preview but cannot publish.

The published value is stored as the Market `site_content` key `catalog_layout_theme`; it is independent of customers, Basket, Orders and payments. The storefront applies the same theme to both the "Shop for your home" category section and the product grid.

Preview uses `?catalog_theme_preview=<theme>` and does not persist.
