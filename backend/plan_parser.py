import re

LEADING_WILDCARD_LIKE = re.compile(r"~~\*?\s*'%")


def parse_plan(raw_json: dict) -> dict:
    """raw_json is one element of psycopg2's fetch for
    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <query> -> {"Plan": {...}, "Execution Time": ..., ...}
    """
    return _walk(raw_json["Plan"])


def _walk(node: dict) -> dict:
    children = [_walk(child) for child in node.get("Plans", [])]
    return {
        "type": node.get("Node Type"),
        "join_type": node.get("Join Type"),
        "filter": node.get("Filter"),
        "relation": node.get("Relation Name"),
        "cost_estimated": node.get("Total Cost", 0.0),
        "time_actual_ms": node.get("Actual Total Time", 0.0),
        "rows_estimated": node.get("Plan Rows", 0),
        "rows_actual": node.get("Actual Rows", 0),
        "loops": node.get("Actual Loops", 1),
        "shared_hit_blocks": node.get("Shared Hit Blocks", 0),
        "shared_read_blocks": node.get("Shared Read Blocks", 0),
        "children": children,
    }


def flag_slow_nodes(tree: dict, threshold_pct: float = 0.2) -> dict:
    """Mark any node whose own time (excluding children) is >= threshold_pct
    of total root time as hot. Own time = node time - sum(children time),
    since Actual Total Time is cumulative including children in Postgres plans.
    """
    total = tree["time_actual_ms"] or 1.0  # avoid div by zero on instant queries
    _annotate(tree, total, threshold_pct)
    return tree


def _annotate(node: dict, total: float, threshold_pct: float) -> float:
    children_time = 0.0
    for child in node["children"]:
        children_time += _annotate(child, total, threshold_pct)
    own_time = max(node["time_actual_ms"] - children_time, 0.0)
    node["own_time_ms"] = own_time
    node["hot"] = (own_time / total) >= threshold_pct
    return node["time_actual_ms"]


def suggest_rewrites(tree: dict) -> list[str]:
    suggestions = []
    _scan_for_suggestions(tree, suggestions)
    return suggestions


def _scan_for_suggestions(node: dict, out: list[str]):
    if node["type"] == "Seq Scan" and node["filter"] and LEADING_WILDCARD_LIKE.search(node["filter"]):
        rel = node["relation"] or "this table"
        out.append(f"Sequential scan on '{rel}' due to a leading-wildcard LIKE ({node['filter']}) — "
                    f"a plain btree index can't serve this; consider a pg_trgm GIN/GIN index.")
    elif node["type"] == "Seq Scan" and node["rows_actual"] > 1000:
        rel = node["relation"] or "this table"
        out.append(f"Sequential scan on '{rel}' returning {node['rows_actual']} rows — "
                    f"consider an index on the filter/join columns.")
    if node["type"] == "Nested Loop" and node["rows_actual"] > 10000:
        out.append("Nested Loop over a large row count — a Hash Join or Merge Join "
                    "may be cheaper; check if a join column is missing an index.")
    if node.get("rows_estimated") and node.get("rows_actual"):
        est, act = node["rows_estimated"], node["rows_actual"]
        if est > 0 and (act / est > 10 or act / est < 0.1):
            out.append(f"{node['type']} row estimate off by {act / est:.1f}x "
                        f"(est {est}, actual {act}) — stats may be stale, try ANALYZE.")
    for child in node["children"]:
        _scan_for_suggestions(child, out)
