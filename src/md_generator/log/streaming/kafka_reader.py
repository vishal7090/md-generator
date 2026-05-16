from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.incremental.checkpoint import load_checkpoint, save_checkpoint
from md_generator.log.incremental.checkpoint import Checkpoint


def iter_kafka_lines(
    brokers: str,
    topic: str,
    group: str,
    checkpoint_path: Path | None = None,
) -> Iterator[str]:
    try:
        from kafka import KafkaConsumer  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("Install mdengine[log-stream-kafka] for Kafka streaming") from e

    cp = load_checkpoint(checkpoint_path) if checkpoint_path else None
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=brokers.split(","),
        group_id=group,
        auto_offset_reset="latest" if cp is None else "earliest",
        enable_auto_commit=True,
    )
    try:
        for msg in consumer:
            line = msg.value.decode("utf-8", errors="replace") if isinstance(msg.value, bytes) else str(msg.value)
            yield line.rstrip("\r\n")
            if checkpoint_path:
                save_checkpoint(
                    checkpoint_path,
                    Checkpoint(path=f"kafka://{topic}", offset=msg.offset),
                )
    finally:
        consumer.close()
