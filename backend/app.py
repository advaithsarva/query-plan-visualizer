
import os
import re
import psycopg2
from flask import Flask, request, jsonify

import plan_parser

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")


def _add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


app.after_request(_add_cors)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def run_explain_analyze(sql: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
            rows = cur.fetchone()[0]  # list containing one plan dict
        conn.rollback()  # EXPLAIN ANALYZE actually runs the query; don't commit any side effects
    return rows[0]


@app.route("/api/explain", methods=["POST", "OPTIONS"])
def explain():
    if request.method == "OPTIONS":
        return _add_cors(app.make_default_options_response())

    sql = request.json.get("query", "").strip()
    if not sql:
        return jsonify({"error": "query is required"}), 400
    if not sql.lower().startswith("select"):
        return jsonify({"error": "only SELECT queries are allowed (EXPLAIN ANALYZE executes the query)"}), 400

    try:
        raw = run_explain_analyze(sql)
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 400

    tree, suggestions, exec_time = build_plan(raw)
    return jsonify({"plan": tree, "suggestions": suggestions, "execution_time_ms": exec_time})


def build_plan(raw: dict) -> dict:
    tree = plan_parser.parse_plan(raw)
    tree = plan_parser.flag_slow_nodes(tree)
    return tree, plan_parser.suggest_rewrites(tree), raw.get("Execution Time")


def guess_index_candidate(sql: str):
    # ponytail: regex heuristic, not a real SQL parser — good enough to pick
    # "FROM table ... WHERE column =" out of the simple queries this tool targets
    table = re.search(r"\bFROM\s+(\w+)", sql, re.IGNORECASE)
    column = re.search(r"\bWHERE\s+(?:\w+\.)?(\w+)\s*(?:=|<=|>=|<|>)", sql, re.IGNORECASE)
    if not table or not column:
        return None
    return table.group(1), column.group(1)


@app.route("/api/compare", methods=["POST", "OPTIONS"])
def compare():
    if request.method == "OPTIONS":
        return _add_cors(app.make_default_options_response())

    sql = request.json.get("query", "").strip()
    if not sql:
        return jsonify({"error": "query is required"}), 400
    if not sql.lower().startswith("select"):
        return jsonify({"error": "only SELECT queries are allowed"}), 400

    candidate = guess_index_candidate(sql)
    if not candidate:
        return jsonify({"error": "couldn't find a 'FROM table ... WHERE column =' pattern to index"}), 400
    table, column = candidate

    try:
        without_raw = run_explain_analyze(sql)
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 400

    # Build the index inside a transaction we never commit, so EXPLAIN ANALYZE
    # sees it but the database is untouched once we roll back.
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE INDEX ON "{table}" ("{column}")')
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
                with_raw = cur.fetchone()[0][0]
            conn.rollback()
    except psycopg2.Error as e:
        return jsonify({"error": f"index candidate {table}.{column} failed: {e}"}), 400

    without_tree, without_sugg, without_time = build_plan(without_raw)
    with_tree, with_sugg, with_time = build_plan(with_raw)

    return jsonify({
        "index_candidate": f"{table}({column})",
        "without_index": {"plan": without_tree, "suggestions": without_sugg, "execution_time_ms": without_time},
        "with_index": {"plan": with_tree, "suggestions": with_sugg, "execution_time_ms": with_time},
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
