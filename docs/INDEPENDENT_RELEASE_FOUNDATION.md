# Independent release foundation

This patch replaces package builders only. It does NOT change the currently deployed Market process or routing. Use it in the source checkout and generate standalone packages. Deploy to separate cPanel Python applications and directories, then cut over routes. Do not overwrite the existing Market directory with a standalone service.

- Market ZIP excludes Scorer, Travel and Sports and removes their mounts and landing routes **in the generated archive only**.
- Scorer ZIP includes `expense_scheduler.py` (missing from the previous allowlist).
- Travel/Sports ZIPs include their own identity helper, database, router, UI, and app entrypoint.
- Market SQLite-to-MySQL migration is separate and **not implemented** here. No Scorer/Travel/Sports database migration is performed.
- Existing public `/scorer`, `/travel`, `/sports` URLs need proxy routing or dedicated subdomains before Market-only cutover.
- Scorer domain engine refactoring is NOT implemented in this foundation; split only after baseline regression tests and transactional contracts are established.
- Store DBs, uploads, logs, secrets and virtual environments outside release ZIP extraction directories.
- GoDaddy must support multiple Python app instances; confirm in cPanel before cutover.
