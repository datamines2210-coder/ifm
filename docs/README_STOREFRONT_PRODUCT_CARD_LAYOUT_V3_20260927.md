# Storefront Product Card Layout v3 — 2026-09-27

Presentation-only hot patch.

- Separates product image, product information and purchase controls into independent card zones.
- Uses a constrained 4:3 desktop image viewport and 1:1 mobile viewport with `object-fit: contain`.
- Product images can no longer determine/overflow the details area.
- Product name, weight and price stay in normal document flow.
- Add to basket / Coming Soon is anchored by flex layout, not absolute positioning.
- Removes the secondary external link from compact cards; Product Quick View remains the detailed interaction.
- Responsive grid: 4 desktop, 3 compact desktop/tablet, 2 mobile, 1 very narrow screen.
- No database, catalog, Basket, authentication or payment behavior changes.
