# Catalog image display fix — 2026-09-20

## Cause
Catalog uploads were correctly written under `static/uploads/catalog` and the database stored URLs such as `/static/uploads/catalog/<file>.png`.
The application did not have a `/static/{path}` route. Its generic SPA file handler already starts at the `static` directory, so a request for `/static/uploads/...` was incorrectly resolved as `static/static/uploads/...` and returned the SPA/index instead of the image.

## Fix
- Added a safe `/static/{path:path}` file route rooted at the application's `static` directory.
- Existing catalog image URLs remain valid; no database migration or re-upload is required.
- The same compatibility route also supports existing Scorer `/static/...` media references when mounted in this combined project.
- Added a regression test that uploads a catalog image and GETs the returned URL byte-for-byte.

Validation: 111 tests passed.
