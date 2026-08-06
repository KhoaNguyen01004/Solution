# Agent Instructions

**Read `CLAUDE.md` first.** It is the primary context file for this repository and carries
the architecture notes, the DB-access and frontend conventions, the Scope Control rules,
and the Definition of Done. This file only adds the graphify rules on top of it.

## graphify

**Standing instruction: query the knowledge graph at `graphify-out/` before grepping or
opening files** for any question about how this codebase fits together. `CLAUDE.md`
§ graphify carries the full command table, the two silent-failure modes (no
per-subcommand `--help`; substring matching with no stemming), and the confidence-tag
rules. Read that section rather than relying on the summary below.

Quick reference: the package is `graphifyy` (three y's), the command is `graphify`.
`query` / `path` / `explain` / `affected` / `god-nodes` read the graph; `graphify update .`
rebuilds it by AST with no LLM cost.

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
