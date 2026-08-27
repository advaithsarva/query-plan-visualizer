# Results

Measured 2026-08-21 against the seeded PostgreSQL 16 container in
`docker-compose.yml` (5,000 customers / 200,000 orders, `orders.customer_id`
deliberately unindexed). Figures below are from that run and have **not been
re-measured since** — the Docker daemon is not available on the machine this
repo currently lives on. The commands that produced them are printed beside
each number so they can be reproduced.

## Functional eval — 8/8, after starting at 6/8

```
$ docker compose up -d
$ python backend/eval_queries.py
8/8 passed
```

Eight realistic queries — missing-index range scan, PK lookup, unindexed
join, aggregation, window function, anti-join, CTE with join and limit,
leading-wildcard `LIKE` — each scored against the plan shape, join type and
suggestions the tool *should* produce.

**The first run scored 6/8, and both failures were real product gaps rather
than test bugs.** That is the result worth reading:

1. `plan_parser.py` never captured Postgres's `Join Type` field (`Anti`,
   `Semi`, `Inner`, ...). It read only `Node Type`, which for an anti-join
   just says `"Hash Join"` — so anti- and semi-joins were **structurally
   invisible** to the tool. Fixed by parsing `Join Type` into every node.
2. The seq-scan suggestion fired only above 1,000 actual rows. A
   leading-wildcard `LIKE '%99%'` scan touching 95 rows went unflagged —
   even though no plain btree index can serve a leading wildcard at *any*
   row count. Added a dedicated regex check (`~~\*?\s*'%`) independent of
   the row-count threshold.

A third bug surfaced alongside them: `seed.sql` called `random()` with no
fixed seed, so a container rebuild silently changed row counts and made one
assertion flaky (31 rows on one run, 5,000+ on another, against the same
threshold). Fixed at the root with `SELECT setseed(0.42);` plus range
predicates that stay clear of the threshold — not by loosening the assertion.

## Measured speedup — 2.8x, with the schema untouched

```
$ curl -s localhost:5000/api/compare \
    -d '{"query":"SELECT * FROM orders WHERE customer_id <= 100"}'
```

| | Node | Time |
|---|---|---|
| Before | Seq Scan | 12.1 ms |
| After (candidate index) | Bitmap Heap Scan | 4.3 ms |

**2.8x**, on 200,000 rows. The candidate index is created inside a
transaction that is never committed; `\d orders` was inspected after the call
to confirm nothing persisted to the real schema.

## Unit tests

```
$ python backend/test_plan_parser.py
$ python backend/test_app.py
```

Both green. `test_plan_parser.py` runs without a database — it works on
captured plan JSON — so it is the only suite here that is still runnable on a
machine with no Docker.

## What is *not* measured

- **No accuracy figure for the suggestion engine on real-world queries.** The
  eval's 8 cases are ones the tool was built against. Nothing measures what
  it misses on queries nobody anticipated, and the 6/8 first run is direct
  evidence that unanticipated shapes do get missed.
- **`guess_index_candidate` is a regex, not a parser** — `FROM table ... WHERE
  column <op>`. It misses multi-join queries and anything without a `WHERE`.
  The 2.8x figure above is from a query it handles.
- **No load or concurrency testing.** Dev servers only (`flask run` /
  `vite dev`), no deployment config, no auth.
- **One database, one schema, one seed.** Every figure comes from the same
  seeded fixture; nothing has been run against a production-shaped workload.
