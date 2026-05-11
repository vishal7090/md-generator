# CFG runtime trace JSON

Codeflow scores CFG paths and flags rare edges using a **flat edge weight map** derived from runtime observations.

## Normalized shape

`normalize_runtime_trace` (see `md_generator.codeflow.graph.hotpath`) accepts a JSON **object** with either or both of:

- `counts`: object mapping string keys `"source_cfg_id->target_cfg_id"` (literal `->`) to numeric weights.
- `edges`: same layout as `counts`; values in the two objects are merged (later keys win on collision).

Keys that do not contain `->` are ignored. Values are coerced to `float`.

## Emitting traces

- **Manual / tests:** `PythonEdgeCounter` in `md_generator.codeflow.runtime.python_edge_counter` builds a compatible `counts` dict.
- **Python scripts:** run under line-level trace mapping with:

  `python -m md_generator.codeflow.runtime.trace_runner -o cfg-runtime-trace.json --line-map line-map.json your_script.py`

  The line map lists `files` entries with `path_suffix` (or `path`) and a `lines` object mapping **1-based line numbers** to **CFG node id strings** (same identifiers as `cfg.json` / IR CFG).

Pass the output file to the scan via `--cfg-runtime-trace` (or `ScanConfig.cfg_runtime_trace`).
