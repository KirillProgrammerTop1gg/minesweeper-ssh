from __future__ import annotations

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
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.game = game
        self.cursor_row = cursor_row
        self.cursor_col = cursor_col
        self.local_player_num = local_player_num
        self.p1_name = p1_name
        self.p2_name = p2_name

    def update_stats(
        self,
        game: MinesweeperGame,
        cursor_row: int,
        cursor_col: int,
        local_player_num: int | None = None,
        p1_name: str | None = None,
        p2_name: str | None = None,
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
        self.refresh(layout=False)

    def render(self) -> Text:
        t = Text()

        if self.game.is_pvp:
            if self.game.status == GameStatus.WON:
                win_text = f" [{self.game.pvp_winner.upper()} WINS!] " if self.game.pvp_winner != "Draw" else " [DRAW MATCH!] "
                t.append(win_text, style="bold white on #16a34a")
            elif self.game.status == GameStatus.READY:
                t.append(" [WAITING FOR MOVE] ", style="bold #94a3b8 on #334155")
            else:
                p = self.game.current_player
                is_my_turn = (p == self.local_player_num)
                if is_my_turn:
                    turn_color = "#2563eb" if p == 1 else "#dc2626"
                    t.append(" [YOUR TURN] ", style=f"bold white on {turn_color}")
                else:
                    t.append(" [OPPONENT'S TURN] ", style="bold #cbd5e1 on #334155")

            t.append("  [PVP Duel] ", style="bold #c084fc")

            p1_score = self.game.player_scores[1]
            p2_score = self.game.player_scores[2]
            p1_label = f"{self.p1_name} (Blue)" if self.local_player_num != 1 else f"YOU (Blue)"
            p2_label = f"{self.p2_name} (Red)" if self.local_player_num != 2 else f"YOU (Red)"

            t.append(f"{p1_label}: ", style="bold #38bdf8")
            t.append(f"{p1_score}   ", style="bold #f8fafc")
            t.append(f"{p2_label}: ", style="bold #f87171")
            t.append(f"{p2_score}   ", style="bold #f8fafc")

            found_total = p1_score + p2_score
            rem = self.game.total_mines - found_total
            t.append("Mines Left: ", style="bold #e2e8f0")
            t.append(f"{rem}/{self.game.total_mines}   ", style="bold #fbbf24")

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
