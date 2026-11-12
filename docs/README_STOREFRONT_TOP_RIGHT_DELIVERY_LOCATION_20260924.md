# Storefront top-right delivery location hot patch — 2026-09-24

Baseline: `indian-family-market-production-20260924-081950.zip`.

Moves the existing Delivering-to control into a unified header-actions group immediately left of the account/login icon on desktop and mobile. The existing location modal, selected PIN/locality state, search bar, bottom navigation, basket, WhatsApp, authentication and backend APIs are unchanged. Long mobile locality text is truncated to protect the account control and brand from overflow. The old sub-navigation location remains hidden to avoid duplicate controls.
