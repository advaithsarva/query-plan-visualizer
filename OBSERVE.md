# Observed session log — query_plan_visualizer

What actually happened in this terminal, in order.

## 1. Scaffolding
- Created `backend/`, `frontend/src/` dirs.
- `databases_query_plan_visualizer.md` → moved/renamed to `CLAUDE.md` (project spec, unedited).
- Wrote stub files with pseudocode: `backend/app.py`, `backend/plan_parser.py`, `frontend/package.json`, `frontend/src/App.jsx`, `frontend/src/PlanTree.jsx`.

## 2. Replaced stubs with real implementations
- `backend/plan_parser.py` — real tree walk of Postgres `EXPLAIN (ANALYZE, FORMAT JSON)` output: `parse_plan`, `flag_slow_nodes` (own-time vs total-time %, marks `hot`), `suggest_rewrites` (seq-scan-on-large-table, nested-loop-large-rows, row-estimate-off-by-10x heuristics).
- `backend/test_plan_parser.py` — assert-based self-check against a canned plan JSON, no DB needed.
- `backend/app.py` — real Flask app: `POST /api/explain` (runs `EXPLAIN ANALYZE`, rejects non-SELECT, rolls back after — EXPLAIN ANALYZE actually executes the query), `GET /api/health`, manual CORS headers (no flask-cors dep).
- `frontend/` — real Vite + React + D3 app: `vite.config.js` (dev proxy `/api` → `localhost:5000`), `index.html`, `src/main.jsx`, `src/index.css`, `src/App.jsx` (query textarea, calls `/api/explain`, renders suggestions), `src/PlanTree.jsx` (d3 tree layout, red nodes = hot, click node for cost/row/buffer breakdown panel).
- `docker-compose.yml` + `seed.sql` — Postgres 16 container, 5,000 customers / 200,000 orders via `generate_series`, **no index on `orders.customer_id`** on purpose so the visualizer has a real seq scan to flag.

## 3. Environment checks
```
python --version   → Python 3.12.1
node --version     → v22.17.0
npm --version      → 10.9.2
psql --version     → not installed (fine, only the Docker container needs it)
docker --version   → Docker version 28.1.1
docker ps           → failed: daemon not running (Docker Desktop was closed)
```

## 4. Started Docker Desktop
```
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# polled `docker ps` every 10s → ready after 30s
```

## 5. Installed dependencies
```
cd frontend && npm install                                   → 101 packages, 2 vulnerabilities (unaddressed, dev-only)
python -m pip install --quiet flask psycopg2-binary          → ok
```

## 6. Brought up Postgres + seed data
```
docker compose up -d
# pulled postgres:16-alpine (~110MB), started container query_plan_visualizer-postgres-1
# waited on pg_isready, then confirmed seed finished:
docker exec query_plan_visualizer-postgres-1 psql -U postgres -c "SELECT count(*) FROM orders;"
→ 200000
```

## 7. Ran the self-check
```
cd backend && python test_plan_parser.py
→ all assertions passed
→ 4 suggestion(s) printed (seq scan, nested loop, 2x row-estimate-off warnings)
```

## 8. Started both servers (background)
```
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres" python app.py
→ Flask running on http://127.0.0.1:5000 (debug mode)

npm run dev
→ Vite ready on http://localhost:5173
```

## 9. Verified end-to-end against the real DB
```
curl -X POST http://localhost:5000/api/explain -d '{"query":"SELECT * FROM orders WHERE customer_id = 42"}'
→ real EXPLAIN ANALYZE result: Seq Scan on orders, hot: true, 11.6ms, 40 rows

curl -X POST http://localhost:5173/api/explain -d '{"query":"SELECT * FROM customers WHERE id = 1"}'
→ confirmed Vite dev proxy correctly forwards to Flask
```

## 10. Opened in VS Code
```
code "C:\Projects\domains\databases\query_plan_visualizer"
```

## 11. Frontend redesign
- Original UI looked generic ("AI dashboard": system font, white cards, blue button). Replaced with a dark DBA-console aesthetic: fake terminal window chrome, IBM Plex Mono + Big Shoulders Display (Google Fonts), amber/green phosphor palette, scanline overlay, HUD panels with corner brackets, pulsing red glow on hot nodes.
- Rewrote `frontend/src/index.css`, `App.jsx`, `PlanTree.jsx`; added font links to `index.html`.
- Verified live via `curl` against the running Vite dev server (200 OK) — visual result not screenshotted, but markup/CSS confirmed serving without errors.

## 12. Moved project to top-level `C:\Projects\query-plan-visualizer`
- Established repo convention in `C:\Projects\PROJECTS.md`: local folder name must equal the GitHub repo name, and `repo-health.sh` only checks top-level folders. Project was nested at `domains/databases/query_plan_visualizer` — moved out.
- `mv` failed twice with "Device or resource busy" — my own shell's cwd was inside the folder being moved (fixed by `cd` out first), then a stale VS Code window/watcher still held a handle after that. Worked around with `cp -r` to the new path + `rm -rf` on the old one; the old empty directory skeleton (`query_plan_visualizer/`, `backend/`) could not be fully removed (still locked) — harmless empty leftover, will clear once the old VS Code window closes.
- Killed the specific Flask process by PID (found via `netstat -ano | grep :5000`) rather than `taskkill /IM python.exe`, since multiple unrelated Python processes were running.
- `docker compose down` (old location) → `docker compose up -d` (new location) — compose project name changed from `query_plan_visualizer_*` to `query-plan-visualizer_*` (Docker derives it from the containing folder name).

## 13. Completed `/api/compare` (was the one remaining CLAUDE.md feature — "side-by-side comparison: with index vs without")
- `guess_index_candidate()` — regex heuristic extracting `table`/`column` from `FROM table ... WHERE column <op>`. First version had a regex bug (`\w*\.?(\w+)` let the greedy `\w*` eat into the capture group, so `customer_id` matched as just `"d"`) — caught immediately by testing against Postgres (`column "d" does not exist`), fixed to `(?:\w+\.)?(\w+)`.
- Implementation builds the candidate index inside a transaction that's rolled back after `EXPLAIN ANALYZE`, so the schema is never actually touched — verified with `\d orders` showing only `orders_pkey` after calling `/api/compare`.
- Confirmed real result: `SELECT * FROM orders WHERE customer_id <= 100` → Seq Scan 14–19ms without an index vs. Bitmap Heap Scan ~0.6ms with one.

## 14. Added tests and an eval suite
- `backend/test_app.py` — integration test via Flask's test client against the live seeded Postgres: health check, input validation (400s), `/api/explain` on a real query, `/api/compare`, and a check that the comparison index never leaks into the schema.
- `backend/eval_queries.py` — 8 realistic queries (missing-index range scan, PK lookup, unindexed join, aggregation, window function, anti-join, CTE+join+limit, leading-wildcard `LIKE`) scored against expected plan shape/join type/suggestions.
- First eval run was 6/8 — caught two real gaps, not test bugs:
  1. `plan_parser.py` never captured Postgres's `Join Type` field, so anti-/semi-joins were structurally invisible (`Node Type` just says `"Hash Join"`). Added `join_type` and `filter` fields to `parse_plan`.
  2. The seq-scan suggestion only fired above 1000 actual rows, so `WHERE name LIKE '%99%'` (95 matching rows) went unflagged — even though a leading-wildcard `LIKE` can *never* use a plain btree index regardless of row count. Added a dedicated `LEADING_WILDCARD_LIKE` regex check in `suggest_rewrites`, independent of the row-count threshold.
- Also found: the original test/suggestion logic assumed `customer_id = 42` always returns 1000+ rows, but `seed.sql` uses `random()` with no fixed seed, so a container rebuild silently changed the row count (this run: 31 rows) and made the assertion flaky. Fixed by adding `SELECT setseed(0.42);` to `seed.sql` for reproducibility, and by switching test/eval queries to range predicates (`customer_id <= 100`) that stay well above the suggestion threshold regardless of exact per-customer variance.
- Rebuilt the Postgres volume (`docker compose down -v && up -d`) to pick up the reseeded, deterministic data. All three checks now pass: `test_plan_parser.py`, `test_app.py`, `eval_queries.py` (8/8).

## 15. Added `.gitignore` and `README.md`
- `.gitignore`: `__pycache__/`, `node_modules/`, `.venv/`, `dist/`, `.env`, `*.log`.
- `README.md`: project description, architecture diagram, run instructions, test/eval instructions, tech stack, known limitations (the regex index-candidate heuristic, dev-servers-only, SELECT-only).

## State at end of session
- Postgres container running at the new location (`docker compose down` to stop it; add `-v` to also drop the seeded volume).
- Flask (`:5000`) running in the background; Vite was stopped during the folder move and not yet restarted — run `npm run dev` in `frontend/` to bring it back.
- `frontend/node_modules` present (copied over in the move); `flask`/`psycopg2-binary` installed into the active Python env (not a venv — ponytail: no venv scaffolding for a throwaway dev session, add one if this becomes longer-lived).
- All three check scripts pass. `/api/compare` is implemented and verified. Nothing left unbuilt from the original `CLAUDE.md` spec except syntax highlighting on the query textarea (cosmetic, not attempted).
