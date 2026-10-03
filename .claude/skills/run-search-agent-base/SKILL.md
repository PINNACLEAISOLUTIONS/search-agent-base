---
name: run-search-agent-base
description: Start, run, screenshot, and smoke-test the OLDTIMECRANK search-agent-base app (FastAPI dashboard + listings scraper). Use when asked to run the server, view the dashboard, take a screenshot, hit its API, or run the fetch/update scraper.
---

OLDTIMECRANK is a FastAPI app (`app.py`) serving a static dashboard (`index.html`) plus a JSON API, backed by SQLite. `fetch_listings.py` is the scraper that fills the DB and rewrites the static JSON files. Drive the server with `curl` and the dashboard with `.claude/skills/run-search-agent-base/shot.mjs` (headless Chromium via the global Playwright).

All paths are relative to the repo root.

## Prerequisites

```bash
pip install fastapi uvicorn                       # server
pip install beautifulsoup4 playwright==1.56.0 playwright-stealth==1.0.6   # scraper only
```

Chromium is preinstalled at `/opt/pw-browsers/chromium`; do not run `playwright install`. Node's global `playwright` is used by `shot.mjs`.

## Run (agent path)

```bash
python3 -m uvicorn app:app --port 8000 > /tmp/app.log 2>&1 &
timeout 30 bash -c 'until curl -sf localhost:8000/api/status >/dev/null; do sleep 1; done'

curl -s localhost:8000/api/status          # {"status":"pending",...} on a fresh DB
curl -s localhost:8000/api/listings        # [] on a fresh DB (dashboard falls back to data/listings.json)
curl -s localhost:8000/api/items-for-sale  # 3 curated items
curl -s -X POST localhost:8000/api/seen/nope   # {"error":"Listing ID not found."}

mkdir -p /tmp/shots
node .claude/skills/run-search-agent-base/shot.mjs                      # -> /tmp/shots/dashboard.png
CLICK='text=Market Discovery Radar' node .claude/skills/run-search-agent-base/shot.mjs http://localhost:8000/ /tmp/shots/radar.png   # full-page after clicking the tab

lsof -ti:8000 -sTCP:LISTEN | xargs -r kill   # stop
```

`shot.mjs` prints the page title, the screenshot path, and any console errors or failed requests. Expect the showroom gallery (3 items) and, on the Radar tab, 12 listings loaded from the static fallback.

## Run the scraper (updater)

Run it in a throwaway copy, not in the repo:

```bash
rm -rf /tmp/copy && mkdir /tmp/copy && git archive HEAD | tar -x -C /tmp/copy && cd /tmp/copy && python3 fetch_listings.py
```

`fetch_listings.py` exports to `./data/*.json`, `./listings.json`, `./leads.json`, `./leads.csv` and `./metadata.json`. These are the tracked files that CI commits.

## Gotchas

- **Running the scraper in the repo clobbers tracked data.** With a fresh local DB it exported 2 listings over the tracked 38-entry files. I ran `git checkout -- data listings.json leads.csv leads.json metadata.json` to undo it. Use the throwaway copy above.
- **Starting the server creates `data/listings.db`** (gitignored). Delete it to reset to a fresh DB.
- **Playwright version must match the browser.** Latest pip `playwright` wants chromium build 1243 and fails with `Executable doesn't exist at /opt/pw-browsers/chromium_headless_shell-1243/...`. Pin `playwright==1.56.0` (matches the preinstalled 1194 build).
- **Craigslist is unreachable from this sandbox.** Every Craigslist source fails with `net::ERR_TUNNEL_CONNECTION_FAILED` (egress proxy), so a full scrape can't be verified here. Only the launch path was confirmed.
- **ESM ignores `NODE_PATH`.** `shot.mjs` resolves the global Playwright via `createRequire(npm root -g)` instead of `import`.
- **Expected console noise in screenshots:** Google Fonts (`ERR_CERT_AUTHORITY_INVALID`), Unsplash/Craigslist image URLs (`ERR_TUNNEL_CONNECTION_FAILED`), and a `/favicon.ico` 404. None are app bugs.

## Test

There is no test suite in this repo.

## Troubleshooting

- **`ERR_MODULE_NOT_FOUND: Cannot find package 'playwright'`**: running a script that does a bare `import 'playwright'`. Use `shot.mjs`, which resolves it from the global root.
- **Port already in use**: `lsof -ti:8000 -sTCP:LISTEN | xargs -r kill`, then restart.
