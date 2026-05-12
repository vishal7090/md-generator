# Error Handling

## Expected Error Classes

- Validation errors for missing files, unsupported options, malformed JSON/YAML, or invalid URLs.
- Dependency errors when an optional extra is not installed.
- Runtime errors from external tools such as Graphviz, browser binaries, OCR engines, or ffmpeg.
- Upload and output size errors for API routes with bounded workspaces.

## API Behavior

FastAPI services should return structured HTTP errors and preserve enough detail for operators to diagnose the failing input, dependency, or configuration.

## CLI Behavior

CLI commands should return non-zero exit codes on failure and write actionable messages to stderr.
