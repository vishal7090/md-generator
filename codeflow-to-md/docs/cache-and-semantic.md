# Caching and semantic embeddings

## Git clone cache (`git_loader`)

- **`--cache-ttl` / `cache_ttl_seconds`:** When greater than zero and `--no-cache-layer` is off, recent clone metadata can skip fetch/pull for the same URL/branch/commit within the TTL window.
- **`--no-cache-layer` / `cache_enabled: false`:** Disables TTL skip behavior and omits per-clone cache metadata writes.
- **`--cache-clear` / `cache_clear_mode`:** Before a scan, `git` or `all` clears the global git clone cache; `semantic`, `unified`, or `all` also clears project `.codeflow_cache` namespaces as applicable.

## Unified / project cache (`cache_manager`)

Versioned JSON artifacts live under `.codeflow_cache/` (for example `semantic_meta` and related namespaces). `cache_clear_mode=unified` targets those layers without re-downloading git remotes.

## Semantic embedding vectors (`embeddings.py`)

Vectors and `manifest.json` are stored under `.codeflow_cache/semantic/<model_slug>/`.

- The manifest includes **`manifest_version`** (bumped when fields or validation rules change), **`model_id`**, per-node content **`hashes`**, **`node_order`**, embedding **`dim`**, **`encoder_backend`**, and **`library_versions`** (e.g. `sentence_transformers`, `torch` when importable).
- A cache hit requires matching `manifest_version`, `model_id`, hashes, and vector shape; any change to embedded text or layout invalidates the row set deterministically.
