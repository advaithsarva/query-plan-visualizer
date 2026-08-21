# ponytail: one flat list + one runner, no eval framework — this is the
# "does the suggestion engine actually catch what it should" report.
#
#   DATABASE_URL=... python eval_queries.py

import re
import sys

import app as app_module
import plan_parser


def any_node_type(tree: dict, needle: str) -> bool:
    if needle.lower() in tree["type"].lower():
        return True
    return any(any_node_type(c, needle) for c in tree["children"])


def any_join_type(tree: dict, needle: str) -> bool:
    if tree.get("join_type") and needle.lower() in tree["join_type"].lower():
        return True
    return any(any_join_type(c, needle) for c in tree["children"])


CASES = [
    {
        "name": "missing_index_range_scan",
        "sql": "SELECT * FROM orders WHERE customer_id <= 100",
        "expect_node": "Seq Scan",
        "expect_suggestion": "Sequential scan",
    },
    {
        "name": "primary_key_lookup",
        "sql": "SELECT * FROM customers WHERE id = 1",
        "expect_node": "Index",
        "expect_no_suggestion": "Sequential scan",
    },
    {
        "name": "join_on_unindexed_fk",
        "sql": "SELECT c.name, o.amount FROM customers c JOIN orders o ON o.customer_id = c.id WHERE c.id <= 50",
        "expect_node": "Seq Scan",
        "expect_suggestion": "Sequential scan",
    },
    {
        "name": "aggregation_groupby",
        "sql": "SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id HAVING SUM(amount) > 5000",
        "expect_node": "Aggregate",
    },
    {
        "name": "window_function_sort",
        "sql": "SELECT customer_id, amount, RANK() OVER (PARTITION BY customer_id ORDER BY amount DESC) FROM orders WHERE amount > 400",
        "expect_node": "Sort",
    },
    {
        "name": "anti_join_not_exists",
        "sql": "SELECT c.id FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.amount > 490)",
        "expect_join_type": "Anti",
    },
    {
        "name": "cte_join_order_by_limit",
        "sql": """WITH big_orders AS (SELECT customer_id, amount FROM orders WHERE amount > 450)
                  SELECT c.name, b.amount FROM big_orders b JOIN customers c ON c.id = b.customer_id
                  ORDER BY b.amount DESC LIMIT 20""",
        "expect_node": "Limit",
    },
    {
        "name": "unanchored_like_no_index_possible",
        "sql": "SELECT * FROM customers WHERE name LIKE '%99%'",
        "expect_node": "Seq Scan",
        "expect_suggestion": "leading-wildcard",
    },
]


def run_case(case: dict) -> tuple[bool, str]:
    try:
        raw = app_module.run_explain_analyze(case["sql"])
    except Exception as e:
        return False, f"query failed: {e}"

    tree = plan_parser.parse_plan(raw)
    tree = plan_parser.flag_slow_nodes(tree)
    suggestions = plan_parser.suggest_rewrites(tree)

    if "expect_node" in case and not any_node_type(tree, case["expect_node"]):
        return False, f"expected a '{case['expect_node']}' node, tree root was '{tree['type']}'"

    if "expect_join_type" in case and not any_join_type(tree, case["expect_join_type"]):
        return False, f"expected a join_type containing '{case['expect_join_type']}', found none"

    if "expect_suggestion" in case:
        needle = case["expect_suggestion"]
        if not any(needle in s for s in suggestions):
            return False, f"expected a suggestion containing '{needle}', got {suggestions}"

    if "expect_no_suggestion" in case:
        needle = case["expect_no_suggestion"]
        if any(needle in s for s in suggestions):
            return False, f"did not expect a suggestion containing '{needle}', got {suggestions}"

    return True, "ok"


def main():
    passed = 0
    for case in CASES:
        ok, detail = run_case(case)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['name']}: {detail}")
        passed += ok

    total = len(CASES)
    print(f"\n{passed}/{total} cases passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
