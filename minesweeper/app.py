from __future__ import annotations

import asyncio
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Footer, Header, Static

from minesweeper.fingerprint import get_client_fingerprint
from minesweeper.game import DIFFICULTIES, GameStatus, MinesweeperGame, format_coord
from minesweeper.leaderboard import (
    add_pvp_score,
    add_singleplayer_score,
    get_pvp_profile,
    update_pvp_nick,
)
from minesweeper.pvp_client import PVPClient
from minesweeper.screens.custom_modal import CustomGameModal
from minesweeper.screens.help_modal import HelpModal
from minesweeper.screens.leaderboard_modal import LeaderboardModal
from minesweeper.screens.matchmaking_modal import MatchmakingModal
from minesweeper.screens.name_modal import NamePromptModal
from minesweeper.widgets.board import BoardWidget
from minesweeper.widgets.command_bar import CommandBar
from minesweeper.widgets.stats import StatsBar


class MinesweeperApp(App):
    TITLE = "Minesweeper"
    SUB_TITLE = "Chess Coordinates • Pacman Navigation • Real-time Ranked PVP"

    CSS = """
    Screen {
        background: #090d16;
        layers: base overlay;
    }

    #top_bar {
        height: 3;
        width: 100%;
        background: #0f172a;
        padding: 0 1;
        align: center middle;
        border-bottom: solid #334155;
    }

    #top_bar Button {
        margin: 0 1;
        min-width: 13;
        height: 3;
    }

    #board_container {
        width: 100%;
        height: 1fr;
        align: center middle;
        overflow: auto auto;
        background: #090d16;
        padding: 1 2;
    }

    BoardWidget {
        background: #090d16;
    }

    #bottom_container {
        dock: bottom;
        height: auto;
    }

    #hint_bar {
        width: 100%;
        height: 1;
        text-align: center;
        background: #0f172a;
        color: #94a3b8;
    }
    """

    BINDINGS = [
        Binding("1", "set_beginner", "1: Beg", show=True),
        Binding("2", "set_intermediate", "2: Mid", show=True),
        Binding("3", "set_expert", "3: Exp", show=True),
        Binding("4", "set_custom", "4: Custom", show=True),
        Binding("5", "set_pvp", "5: PVP", show=True),
        Binding("r", "restart_game", "R: Restart", show=True),
        Binding("l", "show_leaderboard", "L: Scores", show=True),
        Binding("slash", "focus_command", "/: Coord", show=True),
        Binding("h", "show_help", "H: Help", show=True),
        Binding("escape", "focus_board", "Esc: Board", show=False),
        Binding("q", "quit", "Q: Quit", show=True),
        Binding("ctrl+q", "quit", "Ctrl+Q: Quit", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_rows = 9
        self.current_cols = 9
        self.current_mines = 10
        self.current_diff_name = "Beginner"
        self.current_is_pvp = False
        self._score_saved = False

        _, self.player_tag = get_client_fingerprint()
        prof = get_pvp_profile(self.player_tag)
        self.player_nick = prof.get("nick") or f"Player{self.player_tag.replace('#', '')[:4]}"

        self.pvp_client = PVPClient()
        self.is_networked_pvp = False
        self.local_player_num = 1
        self.p1_name = "Player 1"
        self.p2_name = "Player 2"
        self.opp_score = 0
        self.opp_time = 0
        self.opp_cleared = 0
        self.opp_status = "READY"
        self.opp_name = "Opponent"
        self.match_winner: Optional[str] = None
        self.timeout_remaining: int = 30
        self.is_timed_out: bool = False
        self.opp_timed_out: bool = False
        self.last_action_time: float = 0.0

        self.game = MinesweeperGame(
            self.current_rows,
            self.current_cols,
            self.current_mines,
            self.current_diff_name,
            is_pvp=False,
        )
        self.timer = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="top_bar"):
            yield Button("1: Beginner", id="btn_diff_beginner", variant="success")
            yield Button("2: Interm.", id="btn_diff_inter", variant="primary")
            yield Button("3: Expert", id="btn_diff_expert", variant="warning")
            yield Button("4: Custom", id="btn_diff_custom", variant="default")
            yield Button("5: PVP Online", id="btn_diff_pvp", variant="error")
            yield Button("Scores [L]", id="btn_leaderboard", variant="default")
            yield Button("Restart [R]", id="btn_restart", variant="error")
            yield Button("Help [H]", id="btn_help", variant="default")

        yield StatsBar(
            self.game,
            local_player_num=self.local_player_num,
            p1_name=self.p1_name,
            p2_name=self.p2_name,
            opp_score=self.opp_score,
            opp_time=self.opp_time,
            opp_cleared=self.opp_cleared,
            opp_status=self.opp_status,
            opp_name=self.opp_name,
            match_winner=self.match_winner,
            timeout_remaining=self.timeout_remaining,
            is_timed_out=self.is_timed_out,
            opp_timed_out=self.opp_timed_out,
            id="stats_bar",
        )

        with ScrollableContainer(id="board_container"):
            yield BoardWidget(self.game, id="game_board")

        with Vertical(id="bottom_container"):
            yield Static(
                "Controls: [b][O / Enter / Space][/b] Reveal  •  [b][F][/b] Flag  •  [b][C][/b] Chord  •  [b][WASD / Arrows][/b] Move  •  [b]/[/b] Goto  •  [b]Ctrl+Q / Q[/b] Quit",
                id="hint_bar",
            )
            yield CommandBar(id="cmd_bar")
            yield Footer()

    def on_mount(self) -> None:
        self.timer = self.set_interval(1.0, self._on_timer_tick)
        self.query_one(BoardWidget).focus()
        self.pvp_client.on_message = self._on_pvp_message
        self.pvp_client.on_disconnect = self._on_pvp_disconnect

    def _on_timer_tick(self) -> None:
        if self.is_networked_pvp and self.game.status in (GameStatus.PLAYING, GameStatus.READY) and not self.match_winner:
            if self.last_action_time > 0:
                idle = time.time() - self.last_action_time
                self.timeout_remaining = max(0, 30 - int(idle))
            self._sync_stats()
        elif self.game.status == GameStatus.PLAYING:
            self._sync_stats()

    def _sync_stats(self) -> None:
        board = self.query_one(BoardWidget)
        stats = self.query_one(StatsBar)
        stats.update_stats(
            self.game,
            board.cursor_row,
            board.cursor_col,
            local_player_num=self.local_player_num,
            p1_name=self.p1_name,
            p2_name=self.p2_name,
            opp_score=self.opp_score,
            opp_time=self.opp_time,
            opp_cleared=self.opp_cleared,
            opp_status=self.opp_status,
            opp_name=self.opp_name,
            match_winner=self.match_winner,
            timeout_remaining=self.timeout_remaining,
            is_timed_out=self.is_timed_out,
            opp_timed_out=self.opp_timed_out,
        )

    def start_new_game(
        self,
        rows: int,
        cols: int,
        mines: int,
        diff_name: str,
        is_pvp: bool = False,
    ) -> None:
        self.is_networked_pvp = False
        self.opp_score = 0
        self.opp_time = 0
        self.opp_cleared = 0
        self.opp_status = "READY"
        self.opp_name = "Opponent"
        self.match_winner = None
        self.timeout_remaining = 30
        self.is_timed_out = False
        self.opp_timed_out = False
        self.last_action_time = 0.0
        self.current_rows = rows
        self.current_cols = cols
        self.current_mines = mines
        self.current_diff_name = diff_name
        self.current_is_pvp = is_pvp
        self._score_saved = False

        self.game = MinesweeperGame(rows, cols, mines, diff_name, is_pvp=is_pvp)
        container = self.query_one("#board_container", ScrollableContainer)
        board = self.query_one(BoardWidget)
        board.set_game(self.game, local_player_num=1, is_networked_pvp=False)
        container.scroll_to(0, 0, animate=False)
        self._sync_stats()

        mode_desc = "PVP Race" if is_pvp else "Singleplayer"
        self.query_one(CommandBar).show_feedback(
            f"Started: {diff_name} ({cols}x{rows}, {mines} mines) - {mode_desc}"
        )
        board.focus()

    def start_pvp_online_game(self, rows: int, cols: int, mines: int) -> None:
        self.current_rows = rows
        self.current_cols = cols
        self.current_mines = mines
        self.current_diff_name = "PVP Race"
        self.current_is_pvp = True
        self._score_saved = False
        self.opp_score = 0
        self.opp_time = 0
        self.opp_cleared = 0
        self.opp_status = "READY"
        self.match_winner = None
        self.timeout_remaining = 30
        self.is_timed_out = False
        self.opp_timed_out = False
        self.last_action_time = time.time()

        self.game = MinesweeperGame(rows, cols, mines, "PVP Race", is_pvp=True)
        container = self.query_one("#board_container", ScrollableContainer)
        board = self.query_one(BoardWidget)
        board.set_game(self.game, local_player_num=self.local_player_num, is_networked_pvp=True)
        container.scroll_to(0, 0, animate=False)
        self._sync_stats()

        self.query_one(CommandBar).show_feedback(
            "PVP Race started! Identical map. Score safe cells & flags. Don't hit mines!"
        )
        board.focus()

    def _on_pvp_message(self, msg: dict) -> None:
        mtype = msg.get("type")
        if mtype == "state" and self.is_networked_pvp:
            for cell_tuple in msg.get("cells", []):
                r, c, is_rev, is_flag, adj, is_det, is_false = cell_tuple
                cell = self.game.grid[r][c]
                cell.is_revealed = is_rev
                cell.is_flagged = is_flag
                cell.adjacent_mines = adj
                cell.is_detonated = is_det
                cell.is_false_flag = is_false

            st_val = msg.get("my_status")
            if st_val == "PLAYING":
                self.game.status = GameStatus.PLAYING
            elif st_val == "WON":
                self.game.status = GameStatus.WON
            elif st_val == "LOST":
                self.game.status = GameStatus.LOST

            self.game.score = msg.get("my_score", self.game.score)
            self.game.revealed_count = msg.get("my_cleared", self.game.revealed_count)
            self.game.flags_count = msg.get("my_flags", self.game.flags_count)

            my_time = msg.get("my_time", 0)
            if self.game.start_time is None and my_time > 0:
                self.game.start_time = time.time() - my_time
            if self.game.status in (GameStatus.WON, GameStatus.LOST) and self.game.start_time is not None and self.game.end_time is None:
                self.game.end_time = self.game.start_time + my_time

            self.timeout_remaining = msg.get("my_timeout", self.timeout_remaining)
            self.is_timed_out = msg.get("my_timed_out", self.is_timed_out)
            self.opp_timed_out = msg.get("opp_timed_out", self.opp_timed_out)

            self.opp_name = msg.get("opp_nick") or self.opp_name
            self.opp_score = msg.get("opp_score", self.opp_score)
            self.opp_time = msg.get("opp_time", self.opp_time)
            self.opp_cleared = msg.get("opp_cleared", self.opp_cleared)
            self.opp_status = msg.get("opp_status", self.opp_status)

            board = self.query_one(BoardWidget)
            board.refresh(layout=False)
            self._sync_stats()

            last_action = msg.get("last_action", "")
            if last_action:
                self.query_one(CommandBar).show_feedback(last_action)
            elif self.is_timed_out:
                self.query_one(CommandBar).show_feedback("⏱️ Inactivity timeout (30s)! Game Over.", is_error=True)
            elif self.game.status == GameStatus.LOST:
                self.query_one(CommandBar).show_feedback("💥 You detonated! Waiting for opponent to finish...", is_error=True)
            elif self.game.status == GameStatus.WON:
                self.query_one(CommandBar).show_feedback("🎉 Field cleared! Waiting for match result...")

        elif mtype == "game_over" and self.is_networked_pvp:
            self.match_winner = msg.get("winner")
            p1_score = msg.get("p1_score", 0)
            p2_score = msg.get("p2_score", 0)
            my_score = p1_score if self.local_player_num == 1 else p2_score
            opp_score = p2_score if self.local_player_num == 1 else p1_score
            winner_nick = msg.get("winner_nick", "")

            if self.local_player_num == 1:
                self.is_timed_out = msg.get("p1_timed_out", self.is_timed_out)
                self.opp_timed_out = msg.get("p2_timed_out", self.opp_timed_out)
            else:
                self.is_timed_out = msg.get("p2_timed_out", self.is_timed_out)
                self.opp_timed_out = msg.get("p1_timed_out", self.opp_timed_out)

            self._sync_stats()
            self.query_one(BoardWidget).refresh(layout=False)

            if self._score_saved:
                return
            self._score_saved = True

            i_won = (self.match_winner == f"Player {self.local_player_num}")
            if self.match_winner == "Draw":
                title = "🤝 MATCH DRAW! 🤝"
                msg_body = f"Final Score: You {my_score} pts vs Opponent {opp_score} pts"
            elif i_won:
                title = "🏆 VICTORY IN PVP RACE! 🏆"
                if self.opp_timed_out:
                    msg_body = f"Opponent timed out (30s inactivity)!\nFinal Score: You {my_score} pts vs Opponent {opp_score} pts\nEnter your nickname for the global leaderboard:"
                else:
                    msg_body = f"Final Score: You {my_score} pts vs Opponent {opp_score} pts\nEnter your nickname for the global leaderboard:"
            else:
                title = "💥 DEFEAT IN PVP RACE 💥"
                if self.is_timed_out:
                    msg_body = f"You timed out (30s inactivity)!\nWinner: {winner_nick} ({opp_score} pts vs {my_score} pts)"
                else:
                    msg_body = f"Winner: {winner_nick} ({opp_score} pts vs {my_score} pts)"

            def on_pvp_name(name: str | None) -> None:
                if name:
                    self.player_nick = name.strip()
                    update_pvp_nick(self.player_tag, self.player_nick)
                    if self.is_networked_pvp:
                        asyncio.create_task(self.pvp_client.submit_nick(self.player_nick))
                self.push_screen(LeaderboardModal())

            if i_won:
                self.push_screen(
                    NamePromptModal(
                        title,
                        msg_body,
                        default_name=self.player_nick,
                    ),
                    on_pvp_name,
                )
            else:
                self.query_one(CommandBar).show_feedback(msg_body, is_error=True)
                self.push_screen(LeaderboardModal())

        elif mtype == "opponent_cursor" and self.is_networked_pvp:
            r = int(msg.get("r", 0))
            c = int(msg.get("c", 0))
            self.query_one(BoardWidget).set_opponent_cursor(r, c)

        elif mtype == "opponent_disconnected" and self.is_networked_pvp:
            self.query_one(CommandBar).show_feedback(
                msg.get("message", "Opponent disconnected! Victory by forfeit!"),
                is_error=False,
            )

    def _on_pvp_disconnect(self) -> None:
        if self.is_networked_pvp and self.game.status == GameStatus.PLAYING:
            self.query_one(CommandBar).show_feedback("Disconnected from PVP Hub.", is_error=True)

    def action_set_beginner(self) -> None:
        cfg = DIFFICULTIES["beginner"]
        self.start_new_game(cfg.rows, cfg.cols, cfg.mines, "Beginner", is_pvp=False)

    def action_set_intermediate(self) -> None:
        cfg = DIFFICULTIES["intermediate"]
        self.start_new_game(cfg.rows, cfg.cols, cfg.mines, "Intermediate", is_pvp=False)

    def action_set_expert(self) -> None:
        cfg = DIFFICULTIES["expert"]
        self.start_new_game(cfg.rows, cfg.cols, cfg.mines, "Expert", is_pvp=False)

    def action_set_custom(self) -> None:
        def on_custom_configured(result: tuple[int, int, int] | None) -> None:
            if result is not None:
                rows, cols, mines = result
                self.start_new_game(rows, cols, mines, f"Custom {cols}x{rows}", is_pvp=False)

        self.push_screen(CustomGameModal(), on_custom_configured)

    def action_set_pvp(self) -> None:
        def on_match_ready(result: dict | None) -> None:
            if not result:
                return
            if result.get("offline_bot"):
                self.is_networked_pvp = False
                self.start_new_game(16, 16, 40, "Intermediate", is_pvp=False)
                self.query_one(CommandBar).show_feedback("Hub offline. Playing solo mode.", is_error=True)
                return

            self.is_networked_pvp = True
            self.local_player_num = result.get("player_num", 1)
            self.opp_name = result.get("opponent_nick", "Opponent")
            if self.local_player_num == 1:
                self.p1_name = f"{result.get('my_nick', 'Player 1')} ({result.get('my_tag', '')})"
                self.p2_name = f"{result.get('opponent_nick', 'Player 2')} ({result.get('opponent_tag', '')})"
            else:
                self.p1_name = f"{result.get('opponent_nick', 'Player 1')} ({result.get('opponent_tag', '')})"
                self.p2_name = f"{result.get('my_nick', 'Player 2')} ({result.get('my_tag', '')})"

            rows = result.get("rows", 16)
            cols = result.get("cols", 16)
            mines = result.get("mines", 40)
            self.start_pvp_online_game(rows, cols, mines)

        self.push_screen(
            MatchmakingModal(self.pvp_client, self.player_tag, self.player_nick),
            on_match_ready,
        )

    def action_restart_game(self) -> None:
        if self.is_networked_pvp:
            self.action_set_pvp()
        else:
            self.start_new_game(
                self.current_rows,
                self.current_cols,
                self.current_mines,
                self.current_diff_name,
                is_pvp=self.current_is_pvp,
            )

    def action_show_leaderboard(self) -> None:
        self.push_screen(LeaderboardModal())

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_focus_command(self) -> None:
        self.query_one(CommandBar).focus_input()

    def action_focus_board(self) -> None:
        self.query_one(BoardWidget).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn_diff_beginner":
            self.action_set_beginner()
        elif btn_id == "btn_diff_inter":
            self.action_set_intermediate()
        elif btn_id == "btn_diff_expert":
            self.action_set_expert()
        elif btn_id == "btn_diff_custom":
            self.action_set_custom()
        elif btn_id == "btn_diff_pvp":
            self.action_set_pvp()
        elif btn_id == "btn_leaderboard":
            self.action_show_leaderboard()
        elif btn_id == "btn_restart":
            self.action_restart_game()
        elif btn_id == "btn_help":
            self.action_show_help()

    def on_board_widget_cursor_moved(self, event: BoardWidget.CursorMoved) -> None:
        if self.is_networked_pvp:
            self.last_action_time = time.time()
            self.timeout_remaining = 30
            asyncio.create_task(self.pvp_client.send_cursor(event.row, event.col))
        self._sync_stats()

    def on_board_widget_action_triggered(self, event: BoardWidget.ActionTriggered) -> None:
        if self.is_networked_pvp:
            if self.game.status in (GameStatus.WON, GameStatus.LOST):
                return
            self.last_action_time = time.time()
            self.timeout_remaining = 30
            asyncio.create_task(
                self.pvp_client.send_move(event.action, event.row, event.col)
            )
        else:
            self._sync_stats()
            self.query_one(CommandBar).show_feedback(event.message)
            self._check_game_over()

    def on_command_bar_execute_coordinate(self, event: CommandBar.ExecuteCoordinate) -> None:
        board = self.query_one(BoardWidget)
        target_r = event.row if event.row >= 0 else board.cursor_row
        target_c = event.col if event.col >= 0 else board.cursor_col

        if not self.game.is_valid_coord(target_r, target_c):
            self.query_one(CommandBar).show_feedback(
                f"Coordinates out of bounds: {format_coord(target_r, target_c)}", is_error=True
            )
            return

        board.set_cursor(target_r, target_c)

        if self.is_networked_pvp:
            if self.game.status in (GameStatus.WON, GameStatus.LOST):
                return
            self.last_action_time = time.time()
            self.timeout_remaining = 30
            asyncio.create_task(
                self.pvp_client.send_move(event.action, target_r, target_c)
            )
        else:
            if event.action == "flag":
                board.flag_current()
            else:
                board.reveal_current()
            self._sync_stats()
            self._check_game_over()

        board.focus()

    def _check_game_over(self) -> None:
        if self._score_saved:
            return

        if self.is_networked_pvp:
            return

        if self.game.status == GameStatus.WON:
            self._score_saved = True
            elapsed = int(self.game.elapsed_time)
            score = self.game.score

            def on_name_entered(name: str | None) -> None:
                player_name = name or self.player_nick
                add_singleplayer_score(
                    player_name,
                    self.current_diff_name,
                    score,
                    elapsed,
                )
                self.push_screen(LeaderboardModal())

            self.push_screen(
                NamePromptModal(
                    "Field Cleared!",
                    f"Finished in {elapsed}s with score {score}!",
                    default_name=self.player_nick,
                ),
                on_name_entered,
            )

    def on_key(self, event: events.Key) -> None:
        if event.key == "ctrl+q":
            event.stop()
            self.exit()
            return

        focused = self.focused
        if not focused:
            return

        top_buttons = [
            "btn_diff_beginner",
            "btn_diff_inter",
            "btn_diff_expert",
            "btn_diff_custom",
            "btn_diff_pvp",
            "btn_leaderboard",
            "btn_restart",
            "btn_help",
        ]

        if focused.id in top_buttons:
            idx = top_buttons.index(focused.id)
            if event.key == "right":
                event.stop()
                next_id = top_buttons[(idx + 1) % len(top_buttons)]
                self.query_one(f"#{next_id}", Button).focus()
            elif event.key == "left":
                event.stop()
                prev_id = top_buttons[(idx - 1) % len(top_buttons)]
                self.query_one(f"#{prev_id}", Button).focus()
            elif event.key in ("down", "escape"):
                event.stop()
                self.query_one(BoardWidget).focus()


if __name__ == "__main__":
    app = MinesweeperApp()
    app.run()
