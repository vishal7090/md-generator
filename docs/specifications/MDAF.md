# Markdown Artifact Format (MDAF)

MDAF defines how mdengine generators expose AI-retrieval-ready Markdown artifacts.

## Artifact IDs

- `chunk://{namespace}/{type}/{slug}/{seq}` — semantic chunks
- `incident://{hash}` — incident groups
- `artifact_id` must be stable for identical inputs and config

## Frontmatter

Optional YAML block before Markdown body:

```yaml
---
artifact_type: incident
artifact_id: incident://abc123
severity: high
service: auth-api
tags:
  - redis
  - timeout
agent_hints:
  searchable: true
  summarize: true
  root_cause_candidate: true
---
```

## Relations

Artifacts may declare `relations` in JSON export:

- `target_id` — another artifact id
- `relation_type` — e.g. `related_incident`, `same_service`, `trace_link`

## Lineage

Lineage metadata SHOULD include:

- `source_file` — path or archive member
- `line_number` — start line of record
- `offset` — byte offset when incremental processing is enabled

## Validation

Use `md_generator.core.artifacts.mdaf_validate` in tests and CI.
