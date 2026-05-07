# Codeflow graph model and scan outputs

This document describes how `md_generator.codeflow` represents code as a graph and what files a scan writes.

For **GitHub / GitLab / Azure DevOps / Bitbucket** URLs as scan input, clone cache, and auth flags, see [remote-repos.md](remote-repos.md).

## Internal graph (`networkx.DiGraph`)

- **Node IDs** are mostly **symbol IDs**: `relative/path/to/File.ext::QualifiedClass.methodName` (or `path::method` for module-level callables). Nested Java types use dots in the class segment, e.g. `Outer.Inner.method`.
- **Node attributes** (subset): `type` (`method`, `entry`, `unknown`), `class_name`, `method_name`, `file_path` (relative POSIX path), `language`, optional `entry_kind` / `entry_label` for detected entries, `unresolved` for heuristic callee nodes.
- **Edges** include:
  - `relation`: semantic kind — `CALLS` for call edges; optional **`IMPORTS`**, **`INHERITS`**, **`IMPLEMENTS`** (and other values in [`graph/relations.py`](../../src/md_generator/codeflow/graph/relations.py)) when **`--graph-include-structural`** is enabled and the parser emits [`StructuralEdge`](../../src/md_generator/codeflow/models/ir.py) rows (Java: imports + extends / implements).
  - `type`: execution flavour — `sync` or `async` (unchanged for backward compatibility).
  - `confidence`: `1.0` static resolution, `0.7` dynamic, `0.5` unknown/unresolved callee.
  - `condition`, `labels`: branch context (e.g. `if` predicate snippet; else-branch calls often carry label `else`).
  - `resolution`, `unknown_call`, `recursive`, `async_`.

Unresolved callees appear as nodes whose ID starts with `unknown::` or nodes marked `unresolved`.

## Serialized graphs

| File | Description |
|------|-------------|
| `graph-full.json` | Legacy shape: `{ "nodes": [...], "edges": [...] }` with the same attributes as the DiGraph. **Stable for existing tools.** |
| `graph-schema.json` | Optional **stable export** (Node/Edge view with `kind`, derived File/Class/Method hierarchy, `CONTAINS` edges, plus structural edges when merged). Emitted when `--emit-graph-schema` is set and `json` is in `--formats`. |

## Flow analysis

- Slices are **depth-limited** from an entry symbol (`FlowSlice` in `analyzers/flow_analyzer.py`). They are **static** approximations; dynamic dispatch may appear as `unknown::*`.
- `flow-tree.json` (optional) is a **DFS expansion tree** for documentation, not a single runtime path.

## Output layout

- **Default:** one directory per entry **slug** under `--output` (e.g. `out/<slug>/entry.md`, `flow.md`, …).
- **Per-method mode** (`--emit-entry-per-method`): slugs are written under `out/methods/<slug>/`. [`system_overview.md`](../../src/md_generator/codeflow/generators/entry_markdown.py) links use the `methods/` prefix.
- **Root:** `graph-full.json` (if `json` in formats), `system_overview.md` (if `md`), `scan-summary.md` (unless `--no-scan-summary`).

## IR-based CFG (optional)

When **`--emit-cfg`** is set, parsers populate a normalized **IR** (`IRMethod` / `IRStmt` in `md_generator.codeflow.models.ir_cfg`) per file, and for each emitted entry the scan writes:

- `cfg.json` — nodes/edges from the generic CFG builder (`graph/cfg_builder.py`, no AST imports).
- `cfg.mmd` — Mermaid `flowchart` sketch.
- `cfg-paths.md` / `cfg-paths.mmd` — bounded START→END path enumeration (`graph/path_enumerator.py`) plus a path-highlight comment on the first path in Mermaid.
- If Markdown is enabled, **Control-flow graph (IR)** and **Execution paths** sections are appended to `flow.md`.

Adapters: Python (`parsers/adapters/python_adapter.py`), Java (`java_adapter.py`), JS/TS/TSX (`treesitter_adapter.py` when tree-sitter extras are installed). Other languages leave `ir_methods` empty until extended.

Use **`--cfg-max-nodes`** to cap CFG size (default 500). Optional cross-method inlining: **`--cfg-inline-calls`** / **`--no-cfg-inline-calls`** with **`--cfg-call-depth`** (default 3). Path caps: **`--cfg-max-paths`** (100), **`--cfg-path-max-depth`** (1000), **`--cfg-loop-visits`** (2).

## Configuration

- **Formats:** use `--formats` (comma-separated: `md`, `mermaid`, `json`, `html`), not `--output` (which is the **directory**).
- **Liferay / YAML:** extra portlet base class names via `--liferay-portlet-bases` or project `codeflow.yaml` (`liferay.portlet_base_classes`) and optional `--codeflow-config` path.
- **Verbosity:** `--verbose` sets DEBUG logging for `md_generator.codeflow`.

## Graph intelligence (Markdown)

For each entry, `flow.md` and `entry.md` can list **Called by** and **Impact** (call graph) with list caps; see `ScanConfig.intelligence_list_cap`.

- **`--graph-include-structural`**: merge Java structural edges into the DiGraph; **Dependencies** sections list imports / inheritance for the entry’s file and class when data exists.
- **`--intelligence-transitive-callers`**: **Called by** lists transitive callers (`nx.ancestors` on the call-only subgraph) instead of direct predecessors only.
- **`--emit-system-graph-stats`**: append **Graph inventory** (node/edge counts, relation histogram, top call-graph out-degree) to `system_overview.md`.
- **`--emit-llm-entry-sidecar`**: write `entry.llm.md` beside `entry.md` (short links to `entry.md`, `flow.md`, and CFG path docs when enabled).

With **`--verbose`**, `build_graph` logs relation counts at DEBUG after a structural merge.
