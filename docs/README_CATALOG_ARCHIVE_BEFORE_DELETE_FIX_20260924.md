# Catalog archive-before-delete hot patch — 2026-09-24

Fixes the Catalog product multi-select block so its CSS/JavaScript is emitted as executable HTML rather than literal escaped newline text. Administrator product-row checkboxes now render for every visible product.

Permanent bulk deletion is a two-step lifecycle: Administrator must archive selected products first, then select archived products and delete them. The API independently enforces archive-first and continues to block deletion for products referenced by order history. Managers retain Add/Edit privileges and cannot archive/delete.
