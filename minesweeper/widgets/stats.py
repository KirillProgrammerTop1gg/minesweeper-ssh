from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.widget import Widget

from minesweeper.game import GameStatus, MinesweeperGame, format_coord


class StatsBar(Widget):
    DEFAULT_CSS = """
    StatsBar {
        height: 3;
        width: 100%;
        background: #0f172a;
        border: solid #334155;
        padding: 0 1;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        game: MinesweeperGame,
        cursor_row: int = 0,
        cursor_col: int = 0,
        local_player_num: int = 1,
        p1_name: str = "Player 1",
        p2_name: str = "Player 2",
        opp_score: int = 0,
        opp_time: int = 0,
        opp_cleared: int = 0,
        opp_status: str = "READY",
        opp_name: str = "Opponent",
        match_winner: Optional[str] = None,
        timeout_remaining: int = 30,
        is_timed_out: bool = False,
        opp_timed_out: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.game = game
        self.cursor_row = cursor_row
        self.cursor_col = cursor_col
        self.local_player_num = local_player_num
        self.p1_name = p1_name
        self.p2_name = p2_name
        self.opp_score = opp_score
        self.opp_time = opp_time
        self.opp_cleared = opp_cleared
        self.opp_status = opp_status
        self.opp_name = opp_name
        self.match_winner = match_winner
        self.timeout_remaining = timeout_remaining
        self.is_timed_out = is_timed_out
        self.opp_timed_out = opp_timed_out

    def update_stats(
        self,
        game: MinesweeperGame,
        cursor_row: int,
        cursor_col: int,
        local_player_num: int | None = None,
        p1_name: str | None = None,
        p2_name: str | None = None,
        opp_score: int | None = None,
        opp_time: int | None = None,
        opp_cleared: int | None = None,
        opp_status: str | None = None,
        opp_name: str | None = None,
        match_winner: str | None = None,
        timeout_remaining: int | None = None,
        is_timed_out: bool | None = None,
        opp_timed_out: bool | None = None,
    ) -> None:
        self.game = game
        self.cursor_row = cursor_row
        self.cursor_col = cursor_col
        if local_player_num is not None:
            self.local_player_num = local_player_num
        if p1_name is not None:
            self.p1_name = p1_name
        if p2_name is not None:
            self.p2_name = p2_name
        if opp_score is not None:
            self.opp_score = opp_score
        if opp_time is not None:
            self.opp_time = opp_time
        if opp_cleared is not None:
            self.opp_cleared = opp_cleared
        if opp_status is not None:
            self.opp_status = opp_status
        if opp_name is not None:
            self.opp_name = opp_name
        if match_winner is not None:
            self.match_winner = match_winner
        if timeout_remaining is not None:
            self.timeout_remaining = timeout_remaining
        if is_timed_out is not None:
            self.is_timed_out = is_timed_out
        if opp_timed_out is not None:
            self.opp_timed_out = opp_timed_out
        self.refresh(layout=False)

    def render(self) -> Text:
        t = Text()

        if self.game.is_pvp:
            if self.match_winner:
                if self.match_winner == "Draw":
                    t.append(" [DRAW] ", style="bold white on #475569")
                elif self.match_winner == f"Player {self.local_player_num}":
                    t.append(" [VICTORY] ", style="bold white on #16a34a")
                else:
                    t.append(" [DEFEAT] ", style="bold white on #dc2626")
            elif self.is_timed_out:
                t.append(" [TIMEOUT] ", style="bold white on #dc2626")
            elif self.game.status == GameStatus.READY:
                t.append(" [READY] ", style="bold #94a3b8 on #334155")
            elif self.game.status == GameStatus.PLAYING:
                t.append(" [RACING] ", style="bold white on #2563eb")
            elif self.game.status == GameStatus.WON:
                t.append(" [CLEARED] ", style="bold white on #16a34a")
            elif self.game.status == GameStatus.LOST:
                t.append(" [DETONATED] ", style="bold white on #dc2626")

            t.append("  [PVP Race] ", style="bold #c084fc")

            t.append("YOU: ", style="bold #38bdf8")
            t.append(f"{self.game.score:,} pts ", style="bold #fbbf24")
            t.append(f"({self.game.revealed_count}/{self.game.safe_cells_total}) ", style="bold #f8fafc")
            elapsed = self.game.get_elapsed_time()
            mins, secs = divmod(elapsed, 60)
            t.append(f"{mins:02d}:{secs:02d} ", style="bold #38bdf8")

            if self.game.status in (GameStatus.PLAYING, GameStatus.READY) and not self.match_winner and not self.is_timed_out:
                time_left = max(0, int(self.timeout_remaining))
                if time_left > 10:
                    t.append(f"[{time_left}s]  ", style="bold #22c55e")
                elif time_left > 5:
                    t.append(f"[{time_left}s]  ", style="bold #f59e0b")
                else:
                    t.append(f"[{time_left}s]! ", style="bold white on #dc2626")
            else:
                t.append(" ", style="")

            t.append("vs  ", style="dim #94a3b8")

            opp_display = self.opp_name if self.opp_name else "Opponent"
            t.append(f"{opp_display}: ", style="bold #f87171")
            t.append(f"{self.opp_score:,} pts ", style="bold #fbbf24")
            t.append(f"({self.opp_cleared}/{self.game.safe_cells_total}) ", style="bold #f8fafc")
            o_mins, o_secs = divmod(self.opp_time, 60)
            t.append(f"{o_mins:02d}:{o_secs:02d} ", style="bold #38bdf8")

            if self.opp_timed_out:
                t.append("[TIMEOUT]  ", style="bold #ef4444")
            elif self.opp_status == "LOST":
                t.append("[BOOM]  ", style="bold #ef4444")
            elif self.opp_status == "WON":
                t.append("[CLEARED]  ", style="bold #22c55e")
            elif self.opp_status == "PLAYING":
                t.append("[RACING]  ", style="bold #38bdf8")
            else:
                t.append("[READY]  ", style="dim #94a3b8")

            rem_mines = self.game.get_remaining_mines()
            t.append("Mines: ", style="bold #e2e8f0")
            t.append(f"{rem_mines}   ", style="bold #4ade80" if rem_mines >= 0 else "bold #f87171")

            coord = format_coord(self.cursor_row, self.cursor_col)
            t.append("Pos: ", style="bold #94a3b8")
            t.append(f" {coord} ", style="bold #0f172a on #94a3b8")
            return t

        if self.game.status == GameStatus.READY:
            status_text = " [READY] "
            status_style = "bold #38bdf8 on #1e293b"
        elif self.game.status == GameStatus.PLAYING:
            status_text = " [PLAYING] "
            status_style = "bold #fbbf24 on #1e293b"
        elif self.game.status == GameStatus.WON:
            status_text = " [VICTORY] "
            status_style = "bold white on #16a34a"
        else:
            status_text = " [GAME OVER] "
            status_style = "bold white on #dc2626"

        t.append(status_text, style=status_style)
        t.append("  ")
        t.append(f"[{self.game.difficulty_name}] ", style="bold #c084fc")

        t.append("Score: ", style="bold #e2e8f0")
        t.append(f"{self.game.score:,}   ", style="bold #fbbf24")

        remaining_mines = self.game.get_remaining_mines()
        mine_style = "bold #f87171" if remaining_mines < 0 else "bold #4ade80"
        t.append("Mines: ", style="bold #e2e8f0")
        t.append(f"{remaining_mines}   ", style=mine_style)

        elapsed = self.game.get_elapsed_time()
        mins, secs = divmod(elapsed, 60)
        t.append("Time: ", style="bold #e2e8f0")
        t.append(f"{mins:02d}:{secs:02d}   ", style="bold #38bdf8")

        t.append("Cleared: ", style="bold #e2e8f0")
        t.append(f"{self.game.revealed_count}/{self.game.safe_cells_total}   ", style="bold #f8fafc")

        coord = format_coord(self.cursor_row, self.cursor_col)
        t.append("Pos: ", style="bold #94a3b8")
        t.append(f" {coord} ", style="bold #0f172a on #94a3b8")

        return t
