# ponytail: plain assert script using Flask's built-in test client, no pytest
# dependency added. Needs `docker compose up -d` running (real Postgres, seeded).

import app as app_module

client = app_module.app.test_client()


def demo():
    # health check
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"

    # rejects missing query
    r = client.post("/api/explain", json={})
    assert r.status_code == 400

    # rejects non-SELECT (EXPLAIN ANALYZE would execute it)
    r = client.post("/api/explain", json={"query": "DELETE FROM orders"})
    assert r.status_code == 400

    # real query against the live seeded DB — range predicate so the row count
    # (~4000 of 200k, averaged over 100 customers) doesn't depend on exactly
    # which random rows the seed happened to generate for one customer_id
    r = client.post("/api/explain", json={"query": "SELECT * FROM orders WHERE customer_id <= 100"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["plan"]["type"] == "Seq Scan"
    assert body["plan"]["hot"] is True
    assert any("Sequential scan" in s for s in body["suggestions"])

    # pk lookup should not need a seq-scan suggestion
    r = client.post("/api/explain", json={"query": "SELECT * FROM customers WHERE id = 1"})
    assert r.status_code == 200
    body = r.get_json()
    assert "Index" in body["plan"]["type"]

    # compare: with-index plan must be faster and not flag a sequential scan
    r = client.post("/api/compare", json={"query": "SELECT * FROM orders WHERE customer_id <= 100"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["index_candidate"] == "orders(customer_id)"
    assert body["with_index"]["execution_time_ms"] < body["without_index"]["execution_time_ms"]
    assert not any("Sequential scan" in s for s in body["with_index"]["suggestions"])

    # verify the comparison index did not leak into the real schema
    with app_module.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'orders' AND indexname != 'orders_pkey'
            """)
            assert cur.fetchall() == []

    print("all assertions passed")


if __name__ == "__main__":
    demo()
