from __future__ import annotations

import asyncio
from typing import Optional

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator

from minesweeper.pvp_client import PVPClient


class MatchmakingModal(ModalScreen[Optional[dict]]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    MatchmakingModal {
        align: center middle;
    }
    #match_dialog {
        width: 50;
        height: auto;
        border: thick $accent;
        background: #0f172a;
        padding: 1 2;
    }
    #match_title {
        text-align: center;
        text-style: bold;
        color: #38bdf8;
        margin-bottom: 1;
    }
    #match_status {
        text-align: center;
        color: #f8fafc;
        margin-bottom: 1;
    }
    #match_sub {
        text-align: center;
        color: #94a3b8;
        margin-bottom: 1;
    }
    #loading_box {
        height: 3;
        align: center middle;
        margin-bottom: 1;
    }
    #match_buttons {
        height: 3;
        align: center middle;
    }
    #match_buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, pvp_client: PVPClient, my_tag: str, my_nick: str, **kwargs):
        super().__init__(**kwargs)
        self.client = pvp_client
        self.my_tag = my_tag
        self.my_nick = my_nick
        self.match_data: Optional[dict] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="match_dialog"):
            yield Label("⚔️ Ranked PVP Matchmaking", id="match_title")
            yield Label(f"Profile: [bold cyan]{self.my_nick}[/] ([magenta]{self.my_tag}[/])", id="match_sub")
            yield Label("Connecting to server...", id="match_status")
            with Horizontal(id="loading_box"):
                yield LoadingIndicator()
            with Horizontal(id="match_buttons"):
                yield Button("Cancel (Esc)", id="btn_cancel", variant="error")

    async def on_mount(self) -> None:
        self.client.on_message = self._handle_message
        self.client.on_disconnect = self._handle_disconnect

        if not self.client.connected:
            connected = await self.client.connect()
            if not connected:
                self.query_one("#match_status", Label).update(
                    "[bold red]Cannot reach PVP Hub![/]\nPlease check your connection."
                )
                return

        self.query_one("#match_status", Label).update(
            "Searching for opponent online..."
        )
        await self.client.join_queue(self.my_tag, self.my_nick)

    def _handle_message(self, msg: dict) -> None:
        mtype = msg.get("type")
        if mtype == "queue_status":
            waiting = msg.get("waiting", 1)
            self.query_one("#match_status", Label).update(
                f"Waiting for opponent online... ({waiting} queued)"
            )
        elif mtype == "match_start":
            self.match_data = msg
            self.dismiss(msg)

    def _handle_disconnect(self) -> None:
        try:
            self.query_one("#match_status", Label).update(
                "[dim red]Disconnected from hub.[/]"
            )
        except Exception:
            pass

    async def action_cancel(self) -> None:
        if self.client.connected:
            await self.client.cancel_queue()
        self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            await self.action_cancel()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            await self.action_cancel()
