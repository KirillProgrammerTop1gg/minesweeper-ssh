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

        self._message_handlers: list[Callable[[dict], None]] = []
        self._disconnect_handlers: list[Callable[[], None]] = []

    def add_message_handler(self, handler: Callable[[dict], None]) -> None:
        if handler not in self._message_handlers:
            self._message_handlers.append(handler)

    def remove_message_handler(self, handler: Callable[[dict], None]) -> None:
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    def add_disconnect_handler(self, handler: Callable[[], None]) -> None:
        if handler not in self._disconnect_handlers:
            self._disconnect_handlers.append(handler)

    def remove_disconnect_handler(self, handler: Callable[[], None]) -> None:
        if handler in self._disconnect_handlers:
            self._disconnect_handlers.remove(handler)

    @property
    def on_message(self) -> Optional[Callable[[dict], None]]:
        return self._message_handlers[0] if self._message_handlers else None

    @on_message.setter
    def on_message(self, handler: Optional[Callable[[dict], None]]) -> None:
        if handler is not None:
            self.add_message_handler(handler)

    @property
    def on_disconnect(self) -> Optional[Callable[[], None]]:
        return self._disconnect_handlers[0] if self._disconnect_handlers else None

    @on_disconnect.setter
    def on_disconnect(self, handler: Optional[Callable[[], None]]) -> None:
        if handler is not None:
            self.add_disconnect_handler(handler)

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
                    for handler in list(self._message_handlers):
                        try:
                            handler(data)
                        except Exception as e:
                            logger.error(f"Error in message handler: {e}")
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            self.connected = False
            for handler in list(self._disconnect_handlers):
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error in disconnect handler: {e}")

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
