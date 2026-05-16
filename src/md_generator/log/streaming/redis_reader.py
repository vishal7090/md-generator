from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from md_generator.log.incremental.checkpoint import Checkpoint, load_checkpoint, save_checkpoint


def iter_redis_stream_lines(
    url: str,
    stream: str,
    group: str,
    consumer: str = "md-log-1",
    checkpoint_path: Path | None = None,
) -> Iterator[str]:
    try:
        import redis
    except ImportError as e:
        raise ImportError("Install mdengine[log-stream-redis] for Redis streaming") from e

    r = redis.from_url(url)
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError:
        pass
    cp = load_checkpoint(checkpoint_path) if checkpoint_path else None
    last_id = "0-0" if cp is None else str(cp.offset or "0-0")
    while True:
        msgs = r.xreadgroup(group, consumer, {stream: ">"}, count=10, block=5000)
        for _sname, entries in msgs or []:
            for msg_id, fields in entries:
                body = fields.get(b"line") or fields.get("line") or b""
                if isinstance(body, bytes):
                    yield body.decode("utf-8", errors="replace")
                else:
                    yield str(body)
                r.xack(stream, group, msg_id)
                if checkpoint_path:
                    save_checkpoint(checkpoint_path, Checkpoint(path=f"redis://{stream}", offset=msg_id))
                last_id = msg_id
