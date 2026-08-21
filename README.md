# Query Plan Visualizer

Runs `EXPLAIN ANALYZE` against a real PostgreSQL database and renders the
result as an interactive tree — instead of reading raw plan JSON, click
through the tree to see which node is actually slow, why, and what to do
about it.

![status](https://img.shields.io/badge/tests-8%2F8_passing-brightgreen)

## What it does

- Paste a `SELECT`, run it, get back the real execution plan as a clickable tree
- Nodes that account for a disproportionate share of query time are flagged **hot**
- Automatic rewrite suggestions: missing indexes, unindexed joins, leading-wildcard
  `LIKE` patterns that no btree index can serve, and stale-statistics detection
  (estimated vs. actual row counts off by 10x+)
- Side-by-side index comparison — pick a query, the backend builds a candidate
  index inside a transaction it never commits, runs the plan again, and shows
  you the before/after (the index never actually touches your schema)

## Architecture

```
Browser (React + D3, :5173)
   │  POST /api/explain  { query }
   │  POST /api/compare  { query }
   ▼
Flask backend (:5000)
   │  EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <query>
   ▼
PostgreSQL 16 (Docker)
```

## Running it

Requires Docker, Python 3.11+, and Node 18+.

```bash
# 1. Postgres, seeded with 5k customers / 200k orders (no index on orders.customer_id
#    on purpose, so there's something real for the tool to catch)
docker compose up -d

# 2. Backend
pip install -r requirements.txt
cd backend
python app.py            # http://localhost:5000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev               # http://localhost:5173, proxies /api to :5000
```

Open `http://localhost:5173`, run the default query, click a node.

## Tests

```bash
cd backend
python test_plan_parser.py   # pure logic, no DB needed
python test_app.py           # integration test against the live Postgres container
python eval_queries.py       # 8-case suggestion-accuracy eval, see below
```

## Eval

`eval_queries.py` runs 8 realistic queries (missing-index scans, joins,
window functions, anti-joins, CTEs, leading-wildcard `LIKE`) against the live
database and asserts the tool actually flags what it should — not just that
nothing crashes. Currently 8/8. This is what caught two real bugs during
development: the parser wasn't capturing Postgres's `Join Type` field (so
anti-/semi-joins were invisible), and the suggestion engine's row-count
threshold missed leading-wildcard `LIKE` scans that no plain index can ever
fix regardless of row count.

## Tech stack

Python · Flask · psycopg2 · PostgreSQL 16 (Docker) · React · D3.js · Vite

## Known limitations

- `guess_index_candidate` (used by `/api/compare`) is a regex heuristic over
  `FROM table ... WHERE column <op>` — not a real SQL parser. It won't find a
  candidate in queries with multiple joins or no `WHERE` clause.
- Dev servers only; no auth, no deployment config.
- Only `SELECT` queries are accepted (`EXPLAIN ANALYZE` executes whatever you
  give it, so mutating statements are rejected).
