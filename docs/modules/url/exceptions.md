# URL and Web Exceptions

Expected failures include missing optional dependencies, invalid inputs, unsupported source formats, external tool failures, and output write errors.

API callers should receive structured HTTP failures. CLI users should receive a non-zero exit code and actionable terminal output.
