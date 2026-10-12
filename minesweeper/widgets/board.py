from __future__ import annotations

from rich.text import Text
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.widget import Widget

from minesweeper.game import GameStatus, MinesweeperGame, col_to_letter, format_coord

NUMBER_STYLES = {
    1: "bold #38bdf8",
    2: "bold #4ade80",
    3: "bold #f87171",
    4: "bold #818cf8",
    5: "bold #fb923c",
    6: "bold #2dd4bf",
    7: "bold #c084fc",
    8: "bold #cbd5e1",
}


class BoardWidget(Widget):
    DEFAULT_CSS = """
    BoardWidget {
        width: auto;
        height: auto;
        padding: 0 1;
        background: $background;
        content-align: center middle;
    }
    """

    can_focus = True

    class CursorMoved(Message):
        def __init__(self, row: int, col: int, coord_str: str) -> None:
            super().__init__()
            self.row = row
            self.col = col
            self.coord_str = coord_str

    class ActionTriggered(Message):
        def __init__(self, action: str, row: int, col: int, message: str) -> None:
            super().__init__()
            self.action = action
            self.row = row
            self.col = col
            self.message = message

    def __init__(self, game: MinesweeperGame, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game = game
        self.cursor_row = 0
        self.cursor_col = 0
        self.opponent_cursor: tuple[int, int] | None = None
        self.local_player_num: int = 1
        self.is_networked_pvp: bool = False

    def get_content_width(self, container: Size, viewport: Size) -> int:
        num_w = max(2, len(str(self.game.rows)))
        left_num_space = num_w + 1
        return (left_num_space + 1) + self.game.cols * 3 + (left_num_space + 1)

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return self.game.rows + 4

    def set_game(self, game: MinesweeperGame, local_player_num: int = 1, is_networked_pvp: bool = False) -> None:
        self.game = game
        self.cursor_row = 0
        self.cursor_col = 0
        self.opponent_cursor = None
        self.local_player_num = local_player_num
        self.is_networked_pvp = is_networked_pvp
        self.refresh(layout=True)
        self._notify_cursor()

    def set_cursor(self, row: int, col: int, notify: bool = True) -> None:
        if self.game.is_valid_coord(row, col):
            self.cursor_row = row
            self.cursor_col = col
            self.refresh(layout=False)
            if notify:
                self._notify_cursor()

    def set_opponent_cursor(self, row: int, col: int) -> None:
        if self.game.is_valid_coord(row, col):
            self.opponent_cursor = (row, col)
            self.refresh(layout=False)

    def _notify_cursor(self) -> None:
        coord_str = format_coord(self.cursor_row, self.cursor_col)
        self.post_message(self.CursorMoved(self.cursor_row, self.cursor_col, coord_str))

    def move_cursor(self, dr: int, dc: int) -> None:
        new_r = (self.cursor_row + dr) % self.game.rows
        new_c = (self.cursor_col + dc) % self.game.cols
        self.set_cursor(new_r, new_c)

    def reveal_current(self) -> None:
        if self.game.status in (GameStatus.WON, GameStatus.LOST):
            return
        if self.is_networked_pvp:
            self.post_message(self.ActionTriggered("reveal", self.cursor_row, self.cursor_col, ""))
            return
        success, msg = self.game.reveal(self.cursor_row, self.cursor_col)
        self.refresh(layout=False)
        self.post_message(self.ActionTriggered("reveal", self.cursor_row, self.cursor_col, msg))

    def flag_current(self) -> None:
        if self.game.status in (GameStatus.WON, GameStatus.LOST):
            return
        if self.is_networked_pvp:
            self.post_message(self.ActionTriggered("flag", self.cursor_row, self.cursor_col, ""))
            return
        success, msg = self.game.toggle_flag(self.cursor_row, self.cursor_col)
        self.refresh(layout=False)
        self.post_message(self.ActionTriggered("flag", self.cursor_row, self.cursor_col, msg))

    def chord_current(self) -> None:
        if self.game.status in (GameStatus.WON, GameStatus.LOST):
            return
        if self.is_networked_pvp:
            self.post_message(self.ActionTriggered("chord", self.cursor_row, self.cursor_col, ""))
            return
        success, msg = self.game.chord(self.cursor_row, self.cursor_col)
        self.refresh(layout=False)
        self.post_message(self.ActionTriggered("chord", self.cursor_row, self.cursor_col, msg))

    def on_key(self, event: events.Key) -> None:
        key = event.key
        if key in ("up", "w", "ц"):
            self.move_cursor(-1, 0)
            event.stop()
        elif key in ("down", "s", "ы"):
            self.move_cursor(1, 0)
            event.stop()
        elif key in ("left", "a", "ф"):
            self.move_cursor(0, -1)
            event.stop()
        elif key in ("right", "d", "в"):
            self.move_cursor(0, 1)
            event.stop()
        elif key in ("o", "enter", "space", "щ"):
            event.stop()
            self.reveal_current()
        elif key in ("f", "а"):
            event.stop()
            self.flag_current()
        elif key in ("c", "с"):
            event.stop()
            self.chord_current()

    def _coord_from_mouse(self, x: int, y: int) -> tuple[int, int] | None:
        num_w = max(2, len(str(self.game.rows)))
        prefix_chars = num_w + 1 + 1
        row = y - 2
        col = (x - prefix_chars) // 3
        if self.game.is_valid_coord(row, col):
            return row, col
        return None

    def on_click(self, event: events.Click) -> None:
        pos = self._coord_from_mouse(event.x, event.y)
        if pos is None:
            return

        row, col = pos
        self.set_cursor(row, col)

        if event.button == 3 or event.shift or event.ctrl:
            self.flag_current()
        else:
            self.reveal_current()

    def render(self) -> Text:
        rows = self.game.rows
        cols = self.game.cols
        cur_r = self.cursor_row
        cur_c = self.cursor_col
        opp_r, opp_c = self.opponent_cursor if self.opponent_cursor else (-1, -1)

        num_w = max(2, len(str(rows)))
        left_num_space = num_w + 1

        full_text = Text()

        cursor_bg = "#2563eb"
        if self.game.is_pvp:
            cursor_bg = "#2563eb" if self.local_player_num == 1 else "#dc2626"

        t_top = Text(" " * (left_num_space + 1))
        for c in range(cols):
            letter = col_to_letter(c)
            txt = f" {letter} " if len(letter) == 1 else (f" {letter}" if len(letter) == 2 else f"{letter[:3]}")
            style = "bold #ffffff on #334155" if c == cur_c else "bold #94a3b8"
            t_top.append(txt, style=style)
        t_top.append(" " * (left_num_space + 1) + "\n")
        full_text.append(t_top)

        full_text.append(
            Text(" " * left_num_space + "┌" + "───" * cols + "┐" + " " * left_num_space + "\n", style="#475569")
        )

        for r in range(rows):
            row_line = Text()
            r_style = "bold #ffffff on #334155" if r == cur_r else "bold #94a3b8"

            row_line.append(f"{r + 1:>{num_w}} ", style=r_style)
            row_line.append("│", style="#475569")

            for c in range(cols):
                is_cursor = (r == cur_r and c == cur_c)
                is_opp_cursor = (r == opp_r and c == opp_c and not is_cursor)
                cell = self.game.grid[r][c]

                if cell.found_by_player == 1:
                    cell_str = "[1]" if is_cursor else ("(1)" if is_opp_cursor else " 1 ")
                    style = "bold white on #1d4ed8" if is_cursor else "bold #ffffff on #2563eb"
                elif cell.found_by_player == 2:
                    cell_str = "[2]" if is_cursor else ("(2)" if is_opp_cursor else " 2 ")
                    style = "bold white on #b91c1c" if is_cursor else "bold #ffffff on #dc2626"
                elif is_cursor:
                    if cell.is_flagged:
                        cell_str = "[⚑]"
                        style = "bold white on #be123c"
                    elif cell.is_detonated:
                        cell_str = "[*]"
                        style = "bold white on #b91c1c"
                    elif cell.is_false_flag:
                        cell_str = "[X]"
                        style = "bold white on #b91c1c"
                    elif not cell.is_revealed:
                        cell_str = "[·]"
                        style = f"bold white on {cursor_bg}"
                    elif cell.is_mine:
                        cell_str = "[*]"
                        style = "bold #fef08a on #991b1b"
                    elif cell.adjacent_mines > 0:
                        cell_str = f"[{cell.adjacent_mines}]"
                        style = f"bold white on {cursor_bg}"
                    else:
                        cell_str = "[ ]"
                        style = f"bold white on {cursor_bg}"
                elif is_opp_cursor:
                    opp_color = "#dc2626" if self.local_player_num == 1 else "#2563eb"
                    if cell.is_flagged:
                        cell_str = "(⚑)"
                        style = f"bold white on {opp_color}"
                    elif not cell.is_revealed:
                        cell_str = "(·)"
                        style = f"bold white on {opp_color}"
                    elif cell.adjacent_mines > 0:
                        cell_str = f"({cell.adjacent_mines})"
                        style = f"bold white on {opp_color}"
                    else:
                        cell_str = "( )"
                        style = f"bold white on {opp_color}"
                else:
                    if cell.is_flagged:
                        cell_str = " ⚑ "
                        style = "bold #f43f5e"
                    elif cell.is_detonated:
                        cell_str = " * "
                        style = "bold white on #dc2626"
                    elif cell.is_false_flag:
                        cell_str = " X "
                        style = "bold #f43f5e"
                    elif not cell.is_revealed:
                        cell_str = " · "
                        style = "#64748b"
                    elif cell.is_mine:
                        cell_str = " * "
                        style = "bold #fbbf24"
                    elif cell.adjacent_mines > 0:
                        cell_str = f" {cell.adjacent_mines} "
                        style = NUMBER_STYLES.get(cell.adjacent_mines, "bold white")
                    else:
                        cell_str = "   "
                        style = "#334155"

                row_line.append(cell_str, style=style)

            row_line.append("│", style="#475569")
            row_line.append(f" {r + 1:<{num_w}}", style=r_style)
            row_line.append("\n")
            full_text.append(row_line)

        full_text.append(
            Text(" " * left_num_space + "└" + "───" * cols + "┘" + " " * left_num_space + "\n", style="#475569")
        )

        t_bot = Text(" " * (left_num_space + 1))
        for c in range(cols):
            letter = col_to_letter(c)
            txt = f" {letter} " if len(letter) == 1 else (f" {letter}" if len(letter) == 2 else f"{letter[:3]}")
            style = "bold #ffffff on #334155" if c == cur_c else "bold #94a3b8"
            t_bot.append(txt, style=style)
        t_bot.append(" " * (left_num_space + 1))
        full_text.append(t_bot)

        return full_text
