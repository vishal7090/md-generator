from __future__ import annotations


class LogToMdError(Exception):
    """Base error for log-to-md."""


class ConfigurationError(LogToMdError):
    """Invalid YAML, CLI, or preset."""


class ParserError(LogToMdError):
    """Unrecoverable parse failure."""


class EncodingError(LogToMdError):
    """Could not decode bytes with configured fallbacks."""


class WriterError(LogToMdError):
    """Markdown or artifact write failed."""


class AggregationError(LogToMdError):
    """Pandas aggregation failed."""
