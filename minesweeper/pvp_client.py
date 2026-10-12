from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("pvp_client")


class PVPClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9876):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._listener_task: Optional[asyncio.Task] = None
        self.connected = False

        self.on_message: Optional[Callable[[dict], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None

    async def connect(self, timeout: float = 3.0) -> bool:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=timeout,
            )
            self.connected = True
            self._listener_task = asyncio.create_task(self._listen())
            return True
        except Exception as e:
            logger.debug(f"Failed to connect to PVP Hub at {self.host}:{self.port} - {e}")
            self.connected = False
            return False

    async def _listen(self) -> None:
        try:
            while self.connected and self.reader and not self.reader.at_eof():
                line = await self.reader.readline()
                if not line:
                    break
                try:
                    data = json.loads(line.decode("utf-8").strip())
                    if self.on_message:
                        self.on_message(data)
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            self.connected = False
            if self.on_disconnect:
                self.on_disconnect()

    async def send(self, data: dict) -> None:
        if not self.connected or not self.writer or self.writer.is_closing():
            return
        try:
            raw = json.dumps(data) + "\n"
            self.writer.write(raw.encode("utf-8"))
            await self.writer.drain()
        except Exception:
            self.connected = False

    async def join_queue(self, tag: str, nick: str) -> None:
        await self.send({"type": "join_queue", "tag": tag, "nick": nick})

    async def cancel_queue(self) -> None:
        await self.send({"type": "cancel_queue"})

    async def send_move(self, action: str, r: int, c: int) -> None:
        await self.send({"type": "move", "action": action, "r": r, "c": c})

    async def send_cursor(self, r: int, c: int) -> None:
        await self.send({"type": "cursor", "r": r, "c": c})

    async def submit_nick(self, nick: str) -> None:
        await self.send({"type": "submit_nick", "nick": nick})

    async def disconnect(self) -> None:
        self.connected = False
        if self._listener_task:
            self._listener_task.cancel()
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.writer = None
        self.reader = None
