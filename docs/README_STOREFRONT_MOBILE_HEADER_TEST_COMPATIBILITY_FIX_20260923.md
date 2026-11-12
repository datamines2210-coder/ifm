# Storefront mobile header test compatibility fix — 2026-09-23

Hot patch against production baseline `indian-family-market-production-20260922-181059.zip` plus the storefront search/mobile-layout patch.

Changes are limited to `static/index.html`: restores an explicit close-X pseudo element, adds a stable `account-label` hook, and makes the compact mobile account control an explicit flex column while preserving the current search, delivery-location, and square basket layout. No database, authentication, payment, or API changes.
