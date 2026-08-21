# Query Execution Plan Visualizer
**Domain:** Databases · **Tier:** Easier  
**Estimated build time:** 1–2 weeks

## What it is
A tool that takes any SQL query, runs `EXPLAIN ANALYZE` against PostgreSQL, and renders the execution plan as an interactive node tree. Toggle between estimated and actual costs, compare index scan vs sequential scan strategies, and see which nodes are the bottleneck.

## Why build it
Understanding query plans is what separates engineers who write fast queries from those who don't. Demonstrates you can read and reason about database internals, not just write SELECT statements.

## Core features
- SQL input with syntax highlighting
- EXPLAIN ANALYZE output parsed into a tree structure
- Interactive node tree — click any node for cost breakdown
- Side-by-side comparison: with index vs without
- Highlight slowest nodes (cost heatmap)
- Query rewrite suggestions based on plan analysis

## Tech stack
Python · PostgreSQL · Flask · React · D3.js
