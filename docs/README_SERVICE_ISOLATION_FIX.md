# Service mounting correction — 2026-09-19

This package corrects the previous interpretation of service independence.

Travel, Sports and Badminton Scorer continue to run alongside Indian Family Market in the same FastAPI/Uvicorn deployment. Independence means separate data, identity, session and failure boundaries — not removal of their routes.

`app.main` mounts each extended service independently. An import or database-initialization failure in one extended service is caught and logged so the Market can still start. Healthy services remain available normally.

UI routes:
- `/` — Indian Family Market
- `/admin` — Market administration
- `/travel` — Travel
- `/sports` — Sports
- `/scorer` — Badminton Scorer

API identity namespaces remain separate:
- Market: `/api/auth/...`
- Travel: `/api/travel/auth/...`
- Sports: `/api/sports/auth/...`
- Scorer: `/api/scorer/auth/...`

The complete package also carries forward the latest independent Scorer files from the 20260919-1209 package. No service is intentionally disabled by this correction.
