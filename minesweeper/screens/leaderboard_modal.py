from __future__ import annotations

from rich.table import Table
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from minesweeper.leaderboard import get_top_pvp_players, load_leaderboard


class LeaderboardModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("l", "cancel", "Close", show=False),
        Binding("q", "cancel", "Close", show=False),
    ]

    DEFAULT_CSS = """
    LeaderboardModal {
        align: center middle;
    }
    #leaderboard_dialog {
        width: 82;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #leaderboard_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #leaderboard_scroll {
        height: 1fr;
    }
    #btn_close_lb {
        margin-top: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="leaderboard_dialog"):
            yield Label("Hall of Fame & PVP Rankings", id="leaderboard_title")
            with ScrollableContainer(id="leaderboard_scroll"):
                yield Static(self._build_table())
            yield Button("Close (Esc)", id="btn_close_lb", variant="primary")

    def _build_table(self) -> Table:
        data = load_leaderboard()
        top_pvp = get_top_pvp_players(10)

        table = Table(expand=True, box=None)
        table.add_column("#", style="dim", width=4)
        table.add_column("Player", style="bold cyan")
        table.add_column("Tag", style="dim magenta")
        table.add_column("W / L", justify="center")
        table.add_column("Win Rate", justify="right", style="bold green")
        table.add_column("Mines", justify="right", style="bold bright_yellow")

        table.add_row("", "[bold bright_yellow]═══ RANKED PVP CHAMPIONS ═══[/]", "", "", "", "")

        if not top_pvp:
            table.add_row("-", "No PVP matches recorded yet", "-", "- / -", "-", "-")
        else:
            for idx, p in enumerate(top_pvp, start=1):
                w = p.get("wins", 0)
                l = p.get("losses", 0)
                total = w + l
                rate_str = f"{(w / total * 100):.1f}%" if total > 0 else "0.0%"
                table.add_row(
                    str(idx),
                    p.get("nick", "Anonymous"),
                    p.get("tag", "#----"),
                    f"{w}W / {l}L",
                    rate_str,
                    str(p.get("mines_found", 0)),
                )

        table.add_section()
        table.add_row("", "[bold bright_cyan]═══ TOP SINGLEPLAYER SCORES ═══[/]", "", "", "", "")

        sp_list = data.get("singleplayer", [])
        if not sp_list:
            table.add_row("-", "No singleplayer records yet", "-", "-", "-", "-")
        else:
            for idx, entry in enumerate(sp_list[:10], start=1):
                mins, secs = divmod(entry.get("time", 0), 60)
                time_str = f"{mins:02d}:{secs:02d}"
                table.add_row(
                    str(idx),
                    entry.get("name", "Anonymous"),
                    entry.get("difficulty", "Classic"),
                    f"{entry.get('score', 0):,} pts",
                    time_str,
                    entry.get("date", ""),
                )

        pvp_history = data.get("pvp", [])
        if pvp_history:
            table.add_section()
            table.add_row("", "[bold bright_magenta]═══ RECENT DUELS ═══[/]", "", "", "", "")
            for entry in pvp_history[:6]:
                table.add_row(
                    "PVP",
                    f"{entry.get('p1')} vs {entry.get('p2')}",
                    f"Win: {entry.get('winner')}",
                    entry.get("score", ""),
                    "-",
                    entry.get("date", ""),
                )

        return table

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("escape", "q", "l"):
            event.stop()
            self.dismiss(None)
