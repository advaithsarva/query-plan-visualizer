import plan_parser

SAMPLE_EXPLAIN_JSON = {
    "Plan": {
        "Node Type": "Nested Loop",
        "Total Cost": 500.0,
        "Actual Total Time": 120.0,
        "Plan Rows": 100,
        "Actual Rows": 12000,
        "Actual Loops": 1,
        "Plans": [
            {
                "Node Type": "Seq Scan",
                "Relation Name": "orders",
                "Total Cost": 300.0,
                "Actual Total Time": 100.0,
                "Plan Rows": 100,
                "Actual Rows": 5000,
                "Actual Loops": 1,
            },
            {
                "Node Type": "Index Scan",
                "Relation Name": "customers",
                "Total Cost": 10.0,
                "Actual Total Time": 5.0,
                "Plan Rows": 1,
                "Actual Rows": 1,
                "Actual Loops": 5000,
            },
        ],
    },
    "Execution Time": 121.5,
}


def demo():
    tree = plan_parser.parse_plan(SAMPLE_EXPLAIN_JSON)
    assert tree["type"] == "Nested Loop"
    assert len(tree["children"]) == 2
    assert tree["children"][0]["relation"] == "orders"

    tree = plan_parser.flag_slow_nodes(tree, threshold_pct=0.2)
    assert "own_time_ms" in tree
    seq_scan = tree["children"][0]
    assert seq_scan["hot"] is True  # 100ms of 120ms total is way over 20%

    suggestions = plan_parser.suggest_rewrites(tree)
    assert any("Sequential scan" in s for s in suggestions)
    assert any("Nested Loop" in s for s in suggestions)

    print("all assertions passed")
    print(f"{len(suggestions)} suggestion(s):")
    for s in suggestions:
        print(f"  - {s}")


if __name__ == "__main__":
    demo()
