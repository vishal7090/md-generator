# Log pipeline

Orchestration lives in `md_generator.log.core.pipeline` and is invoked by `extract_to_markdown`.

Optional stages are controlled by YAML feature flags (`incidents`, `chunking`, `embeddings`, `correlation`, `knowledge_graph`, `timeline`, `intelligence`).
