from __future__ import annotations

import asyncio
from collections.abc import Iterator
from queue import Empty, Queue


def iter_websocket_lines(url: str) -> Iterator[str]:
    try:
        import websockets
    except ImportError as e:
        raise ImportError("Install mdengine[log-stream-ws] for WebSocket streaming") from e

    q: Queue[str | None] = Queue()

    async def _run() -> None:
        async with websockets.connect(url) as ws:
            async for message in ws:
                q.put(str(message).rstrip("\r\n"))

    loop = asyncio.new_event_loop()
    task = loop.create_task(_run())

    def pump() -> None:
        loop.run_until_complete(task)

    import threading

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    while True:
        try:
            item = q.get(timeout=1.0)
        except Empty:
            continue
        if item is None:
            break
        yield item
