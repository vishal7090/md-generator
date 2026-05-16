from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig, StreamingSection


def iter_stream_lines(cfg: LogRunConfig | StreamingSection, *, path: Path | None = None) -> Iterator[str]:
    section = cfg.streaming if hasattr(cfg, "streaming") else cfg
    src = (section.source or "tail").lower()
    ck = Path(section.kafka_group + ".checkpoint.json") if hasattr(section, "kafka_group") else None
    if src == "stdin":
        from md_generator.log.streaming.stdin_reader import iter_stdin_lines

        yield from iter_stdin_lines()
    elif src == "kafka":
        from md_generator.log.streaming.kafka_reader import iter_kafka_lines

        yield from iter_kafka_lines(
            section.kafka_brokers,
            section.kafka_topic,
            section.kafka_group,
            checkpoint_path=ck,
        )
    elif src == "redis":
        from md_generator.log.streaming.redis_reader import iter_redis_stream_lines

        yield from iter_redis_stream_lines(
            section.redis_url,
            section.redis_stream,
            section.redis_group,
            checkpoint_path=ck,
        )
    elif src == "websocket":
        from md_generator.log.streaming.websocket_reader import iter_websocket_lines

        yield from iter_websocket_lines(section.websocket_url)
    elif path is not None:
        from md_generator.log.streaming.tail_reader import iter_tail_lines

        yield from iter_tail_lines(path)
    else:
        raise ValueError("tail stream requires --input path")
