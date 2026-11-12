# Multi-Service Architecture — theindianfamily.shop

**Audience:** customers, B2B partners, and acquirers evaluating the platform.
**Scope:** how the main storefront and the extended services (`/travel`, `/sports`, `/scorer`) are designed, released, and operated independently.

---

## 1. Design principle: brand-neutral core, independent services

The production domain **https://theindianfamily.shop/** hosts one main business — the grocery
storefront — plus a set of **extended services** that are deliberately built as independent,
pluggable modules rather than tightly-coupled features.

```text
                         theindianfamily.shop
                                 |
                +----------------+----------------+
                |                |                 |
        Main storefront   Extended service    Extended service ...
        (brand-configurable)  /travel            /sports, /scorer
                |                |                 |
         own DB + users    static content     own DB + users
                                              (scorer.db, own auth)
```

Each box above can be deployed, versioned, tested, patched, or decommissioned **without touching
the others**. This directly supports:

- Merger/acquisition readiness (rebrand or detach the storefront in minutes).
- B2B/white-label resale of a single service (e.g. license only the Scorer app).
- Independent uptime — a defect or outage in one service never takes down another.

---

## 2. Configurable brand identity (merger/acquisition ready)

The storefront name is **not hardcoded**. It is a single configuration value:

```python
# app/config.py
class Settings(BaseSettings):
    app_name: str = "Indian Family Market"   # override via APP_NAME env var / .env
    parent_catalog_url: str = "https://theindianfamily.com/"
```

- All storefront HTML pages (`index.html`, `admin.html`, `travel.html`, `sports.html`) render the
  brand name from a `{{BRAND_NAME}}` template token, substituted server-side from `settings.app_name`
  (see `branded_page()` in `app/main.py`).
- A public, read-only endpoint exposes the same identity for any other consumer (partner sites,
  future acquirer tooling, monitoring dashboards):

  ```http
  GET /api/config
  {"app_name": "Indian Family Market", "environment": "production", "parent_catalog_url": "https://theindianfamily.com/"}
  ```

- To rebrand or transfer ownership: set `APP_NAME` (and, if relevant, `PARENT_CATALOG_URL`) in the
  environment and redeploy. No template or code edits are required.

---

## 3. Service independence contract

Every extended service under `/travel`, `/sports`, `/scorer` (and any future `/<service>`) must satisfy:

| Requirement | How it is implemented today |
|---|---|
| No dependency on other services being up/healthy | Each route serves its own static bundle or its own FastAPI router; no service calls another at runtime. |
| Plug-and-play into any project/domain | Each service is a self-contained folder (`static/<service>.html` + `app/<service>/`) with its own router mounted via `app.include_router(...)`. Moving it to another host means copying that folder + router registration. |
| Own release/patch design | Fixes are shipped as standalone, dated scripts under `fixes/` and `patch/` (e.g. `apply_scorer_*` patches never touch travel/sports/storefront files). |
| Separate dev vs prod data | Storefront uses `DATABASE_URL` (`sqlite:///./indian_family_market.db` by default). Scorer, Travel and Sports each use their own env var (`SCORER_DB_PATH`, `TRAVEL_DB_PATH`, `SPORTS_DB_PATH`), fully independent connections/schemas. `tests/conftest.py` further isolates every test run into a unique temp DB per service. |
| Own testing standard | `tests/test_app.py` covers the storefront routes; `tests/test_scorer.py`, `tests/test_travel.py` and `tests/test_sports.py` each cover their own service end-to-end, isolated from one another. |
| Packaging only what's needed for release | `pkg/`, `release/`, `finalstat*/`, `final_button_safe_patch/` folders hold curated, production-scoped file sets per release — not the whole repo — so a service can be promoted without shipping unrelated code. |
| Clean decommission | Because there are no shared imports or shared tables between services, removing a service means: delete its route registration, delete its static bundle/router folder, delete its data file. Nothing else in the app changes. |
| Own user/account/payment management | Storefront auth (`app/auth.py`, `app/db.py` users table) is separate from Scorer auth (`app/scorer/auth.py`, its own `players`/`scorer_sessions` tables). Travel and Sports ship their own content databases (`app/travel/database.py`, `app/sports/database.py`) but no dedicated accounts yet — their admin-only write endpoints reuse the storefront's admin/manager token; adding full logins to either would use its own dedicated auth boundary, mirroring the Scorer pattern, never reusing the storefront's user table. |

---

## 4. Current service inventory

### 4.1 Main storefront (`/`)
- Grocery discovery, cart, checkout, Razorpay payments, customer accounts.
- Data: `indian_family_market.db` (configurable via `DATABASE_URL`).
- Brand: configurable (`APP_NAME`).

### 4.2 Travel (`/travel`)
- Content service backed by its own SQLite database ([app/travel/database.py](../app/travel/database.py)):
  `travel_packages`, `travel_inquiries`.
- Own router ([app/travel/router.py](../app/travel/router.py)) under `/api/travel` — public read endpoints
  for packages, a public inquiry submission endpoint, and admin-protected write endpoints (reusing the
  storefront's admin/manager token; Travel has no accounts of its own).
- Data: `travel_data/travel.db` (configurable via `TRAVEL_DB_PATH`), fully isolated from every other
  service's database — no shared tables, no shared users table.
- Can be replaced by a fully separate travel booking backend later without touching `/`, `/sports`, or `/scorer`.

### 4.3 Sports (`/sports`)
- Content + community service backed by its own SQLite database ([app/sports/database.py](../app/sports/database.py)):
  `sports_communities`, `sports_posts` (events/blogs/community posts), `sports_inquiries`.
- Own router ([app/sports/router.py](../app/sports/router.py)) under `/api/sports` — public read endpoints
  for communities/posts, a public inquiry submission endpoint, and admin-protected write endpoints (same
  admin/manager token pattern as Travel; no dedicated Sports accounts yet).
- Data: `sports_data/sports.db` (configurable via `SPORTS_DB_PATH`), fully isolated from every other
  service's database. Deep links into `/scorer` for the Badminton community remain unchanged.

### 4.4 Scorer (`/scorer`)
- Full independent service: own FastAPI router (`app/scorer/router.py`), own SQLite database
  (`scorer_data/scorer.db`), own auth/session/roles (admin, scorer, read-only), own statistics and
  ranking engine.
- Reference implementation for "how to add a new independent service" (see §5).

---

## 5. Adding a new independent service (playbook)

1. Create `app/<service>/` with its own `router.py`, `database.py` (own DB file/env var), and `auth.py`
   if the service needs its own accounts.
2. Create `static/<service>.html` as a self-contained page (own CSS/JS, no shared globals).
3. Register the route in `app/main.py`:
   ```python
   app.include_router(<service>_router)
   @app.get("/<service>", include_in_schema=False)
   def <service>_page():
       return branded_page("<service>.html")  # or a service-specific template helper
   ```
4. Add `tests/test_<service>.py` covering the service end-to-end, independent of other test files.
5. Define an env var for its database path/URL, defaulting to a service-scoped file
   (e.g. `<SERVICE>_DB_PATH`), never the storefront's `DATABASE_URL`.
6. Package only the files this service needs when producing a release build (mirror `pkg/`).

---

## 6. Data refresh & environment policy

| Environment | Storefront DB | Scorer DB | Travel DB | Sports DB | Notes |
|---|---|---|---|---|---|
| Local dev | `./indian_family_market.db` | `./scorer_data/scorer.db` | `./travel_data/travel.db` | `./sports_data/sports.db` | Created on first run via each service's `init_db()` |
| Automated tests | temp file, unique per run (`tests/conftest.py`) | temp file, unique per run | temp file, unique per run | temp file, unique per run | Never touches dev or prod data |
| Production (hosting) | path set via `DATABASE_URL` secret | path set via `SCORER_DB_PATH` secret | path set via `TRAVEL_DB_PATH` secret | path set via `SPORTS_DB_PATH` secret | Must differ from dev/test paths |

Refresh policy: production data is **never overwritten by a dev→prod push**. Promoting a new
release only ships code/static assets (see `pkg/`/`release/`); database files are excluded from
release packaging and are migrated in place via `init_db()`'s additive `ALTER TABLE` migrations.
A prod→dev data refresh (for debugging) is a deliberate, one-way export/import step — never automatic.

---

## 7. Decommissioning a service

To retire a service (e.g. `/travel`):
1. Remove its route(s) from `app/main.py`.
2. Remove `static/travel.html` (and `app/travel/` if it had a backend module).
3. Archive or delete its data file, if any.
4. Remove its nav link from `static/index.html`.
5. No other service requires changes — verified by the independence contract in §3.

---

## 8. Release & patch management observed in this repo

- `fixes/apply_*.ps1` — one change, one script, one service (naming makes the target service explicit).
- `patch/*.md` — dated release notes per patch, scoped to the affected service/module.
- `pkg/`, `release/`, `finalstat*/`, `final_button_safe_patch/` — curated production file sets per
  release, so a promotion only ships the files a given service actually needs.

This structure is the working model for "each service has its own patching, release, and
modernization lifecycle" going forward.

## Identity isolation update (2026-09-19)
The current implementation uses a separate identity/security boundary for Market, Scorer, Travel and Sports. See `docs/INDEPENDENT_SERVICE_IDENTITY.md` for database ownership, administrator/user management, service-local sessions, backup/refresh and spin-off rules. Older statements that Travel/Sports reuse storefront authentication are superseded by that document.
