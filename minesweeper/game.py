from __future__ import annotations

import enum
import random
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple


class GameStatus(enum.Enum):
    READY = "READY"
    PLAYING = "PLAYING"
    WON = "WON"
    LOST = "LOST"


@dataclass
class DifficultyPreset:
    name: str
    rows: int
    cols: int
    mines: int


DIFFICULTIES = {
    "beginner": DifficultyPreset("Beginner", 9, 9, 10),
    "intermediate": DifficultyPreset("Intermediate", 16, 16, 40),
    "expert": DifficultyPreset("Expert", 16, 30, 99),
}


def col_to_letter(col: int) -> str:
    result = []
    col += 1
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result.append(chr(65 + rem))
    return "".join(reversed(result))


def letter_to_col(letters: str) -> int:
    s = letters.strip().upper()
    if not s:
        raise ValueError("Empty column coordinate.")
    res = 0
    for ch in s:
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"Invalid column character: '{ch}'")
        res = res * 26 + (ord(ch) - ord("A") + 1)
    return res - 1


def format_coord(row: int, col: int) -> str:
    return f"{col_to_letter(col)}{row + 1}"


def parse_command(cmd_text: str) -> Tuple[str, int, int]:
    cmd = cmd_text.strip().lower()
    if not cmd:
        raise ValueError("Empty command.")

    action = "open"
    flag_match = re.match(r"^(f\s+|flag\s+|f:|!)\s*(.+)$", cmd)
    if flag_match:
        action = "flag"
        cmd = flag_match.group(2).strip()
    else:
        open_match = re.match(r"^(o\s+|open\s+|o:)\s*(.+)$", cmd)
        if open_match:
            action = "open"
            cmd = open_match.group(2).strip()

    m1 = re.match(r"^([a-z]+)\s*(\d+)$", cmd)
    if m1:
        col_str, row_str = m1.groups()
        return action, int(row_str) - 1, letter_to_col(col_str)

    m2 = re.match(r"^(\d+)\s*([a-z]+)$", cmd)
    if m2:
        row_str, col_str = m2.groups()
        return action, int(row_str) - 1, letter_to_col(col_str)

    raise ValueError(f"Invalid coordinate: '{cmd_text}'. Try B5 or F B5")


@dataclass
class Cell:
    is_mine: bool = False
    is_revealed: bool = False
    is_flagged: bool = False
    adjacent_mines: int = 0
    is_detonated: bool = False
    is_false_flag: bool = False
    found_by_player: Optional[int] = None


class MinesweeperGame:
    def __init__(
        self,
        rows: int = 9,
        cols: int = 9,
        mines: int = 10,
        difficulty_name: str = "Beginner",
        is_pvp: bool = False,
        preset_mines: Optional[Set[Tuple[int, int]]] = None,
    ):
        self.rows = max(4, rows)
        self.cols = max(4, cols)
        max_mines = self.rows * self.cols - 1
        self.total_mines = max(1, min(mines, max_mines))
        self.difficulty_name = difficulty_name
        self.is_pvp = is_pvp
        self.preset_mines = set(preset_mines) if preset_mines is not None else None

        self.grid: List[List[Cell]] = []
        self.status = GameStatus.READY
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.moves_count = 0
        self.flags_count = 0
        self.revealed_count = 0
        self.safe_cells_total = self.rows * self.cols - self.total_mines
        self.score = 0

        self.current_player = 1
        self.player_scores = {1: 0, 2: 0}
        self.pvp_winner: Optional[str] = None

        self.reset()

    def reset(self) -> None:
        self.grid = [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]
        self.status = GameStatus.READY
        self.start_time = None
        self.end_time = None
        self.moves_count = 0
        self.flags_count = 0
        self.revealed_count = 0
        self.score = 0
        self.current_player = 1
        self.player_scores = {1: 0, 2: 0}
        self.pvp_winner = None

        if self.preset_mines is not None:
            for r, c in self.preset_mines:
                if self.is_valid_coord(r, c):
                    self.grid[r][c].is_mine = True
            self.total_mines = len(self.preset_mines)
            self.safe_cells_total = self.rows * self.cols - self.total_mines
            self._recalc_adjacent()
        else:
            self.safe_cells_total = self.rows * self.cols - self.total_mines

    def _recalc_adjacent(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.grid[r][c].is_mine:
                    self.grid[r][c].adjacent_mines = sum(
                        1 for nr, nc in self.get_neighbors(r, c) if self.grid[nr][nc].is_mine
                    )
                else:
                    self.grid[r][c].adjacent_mines = 0

    def _relocate_mine(self, old_r: int, old_c: int) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) != (old_r, old_c) and not self.grid[r][c].is_mine:
                    self.grid[old_r][old_c].is_mine = False
                    self.grid[r][c].is_mine = True
                    self._recalc_adjacent()
                    return

    def is_valid_coord(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_neighbors(self, r: int, c: int) -> List[Tuple[int, int]]:
        neighbors = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if self.is_valid_coord(nr, nc):
                    neighbors.append((nr, nc))
        return neighbors

    def _generate_mines(self, safe_r: int, safe_c: int) -> None:
        all_cells = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        neighbors_and_self = set(self.get_neighbors(safe_r, safe_c))
        neighbors_and_self.add((safe_r, safe_c))

        available_cells = [cell for cell in all_cells if cell not in neighbors_and_self]
        if len(available_cells) >= self.total_mines:
            mine_locations = set(random.sample(available_cells, self.total_mines))
        else:
            available_cells = [cell for cell in all_cells if cell != (safe_r, safe_c)]
            mine_locations = set(random.sample(available_cells, self.total_mines))

        for r, c in mine_locations:
            self.grid[r][c].is_mine = True

        for r in range(self.rows):
            for c in range(self.cols):
                if not self.grid[r][c].is_mine:
                    self.grid[r][c].adjacent_mines = sum(
                        1 for nr, nc in self.get_neighbors(r, c) if self.grid[nr][nc].is_mine
                    )

    def start_if_needed(self, r: int, c: int) -> None:
        if self.status == GameStatus.READY:
            if self.preset_mines is None:
                self._generate_mines(r, c)
            self.status = GameStatus.PLAYING
            self.start_time = time.time()

    def get_elapsed_time(self) -> int:
        if self.start_time is None:
            return 0
        if self.end_time is not None:
            return max(0, int(self.end_time - self.start_time))
        return max(0, int(time.time() - self.start_time))

    def get_remaining_mines(self) -> int:
        return self.total_mines - self.flags_count

    def reveal(self, r: int, c: int) -> Tuple[bool, str]:
        if self.status in (GameStatus.WON, GameStatus.LOST):
            return False, "Game is already finished."

        if not self.is_valid_coord(r, c):
            return False, f"Coordinates out of bounds: {format_coord(r, c)}"

        cell = self.grid[r][c]

        if cell.is_flagged:
            return False, "Cell is flagged. Unflag with [F] before opening."

        if cell.is_revealed:
            if cell.adjacent_mines > 0:
                return self.chord(r, c)
            return False, "Cell is already revealed."

        self.start_if_needed(r, c)
        self.moves_count += 1

        if cell.is_mine:
            cell.is_detonated = True
            self.status = GameStatus.LOST
            self.end_time = time.time()
            self._reveal_all_mines()
            return True, "BOOM! You detonated a mine! Game Over."

        newly_revealed = self._flood_fill_reveal(r, c)
        self.revealed_count += newly_revealed
        self.score += newly_revealed * 10
        if newly_revealed > 1:
            self.score += newly_revealed * 5

        if self.revealed_count >= self.safe_cells_total:
            self._trigger_win()
            return True, "VICTORY! All safe cells cleared!"

        return True, f"Opened {format_coord(r, c)}"


    def _flood_fill_reveal(self, start_r: int, start_c: int) -> int:
        queue = [(start_r, start_c)]
        visited: Set[Tuple[int, int]] = {(start_r, start_c)}
        count = 0

        while queue:
            r, c = queue.pop(0)
            cell = self.grid[r][c]

            if cell.is_flagged:
                continue

            if not cell.is_revealed:
                cell.is_revealed = True
                count += 1

            if cell.adjacent_mines == 0 and not cell.is_mine:
                for nr, nc in self.get_neighbors(r, c):
                    if (nr, nc) not in visited:
                        n_cell = self.grid[nr][nc]
                        if not n_cell.is_revealed and not n_cell.is_flagged:
                            visited.add((nr, nc))
                            queue.append((nr, nc))

        return count

    def toggle_flag(self, r: int, c: int) -> Tuple[bool, str]:
        if self.status in (GameStatus.WON, GameStatus.LOST):
            return False, "Game is already finished."

        if not self.is_valid_coord(r, c):
            return False, f"Coordinates out of bounds: {format_coord(r, c)}"

        cell = self.grid[r][c]
        if cell.is_revealed:
            return False, "Cannot flag a revealed cell."

        if self.status == GameStatus.READY:
            self.status = GameStatus.PLAYING
            self.start_time = time.time()

        cell.is_flagged = not cell.is_flagged
        if cell.is_flagged:
            self.flags_count += 1
            if cell.is_mine:
                self.score += 25
            else:
                self.score = max(0, self.score - 10)
            msg = f"Flag placed on {format_coord(r, c)}"
        else:
            self.flags_count -= 1
            if cell.is_mine:
                self.score = max(0, self.score - 25)
            else:
                self.score += 10
            msg = f"Flag removed from {format_coord(r, c)}"

        self.moves_count += 1
        return True, msg

    def chord(self, r: int, c: int) -> Tuple[bool, str]:
        if self.status != GameStatus.PLAYING:
            return False, "Game is not in progress."

        cell = self.grid[r][c]
        if not cell.is_revealed or cell.adjacent_mines == 0:
            return False, "Chording only works on a revealed numbered cell."

        neighbors = self.get_neighbors(r, c)
        flagged_neighbors = [pos for pos in neighbors if self.grid[pos[0]][pos[1]].is_flagged]

        if len(flagged_neighbors) != cell.adjacent_mines:
            return False, f"Chording needs {cell.adjacent_mines} flags (currently {len(flagged_neighbors)})."

        to_reveal = [
            pos for pos in neighbors
            if not self.grid[pos[0]][pos[1]].is_revealed and not self.grid[pos[0]][pos[1]].is_flagged
        ]

        if not to_reveal:
            return False, "All neighbors are already revealed or flagged."

        self.moves_count += 1
        hit_mine = False
        newly_revealed = 0

        for nr, nc in to_reveal:
            n_cell = self.grid[nr][nc]
            if n_cell.is_mine:
                n_cell.is_detonated = True
                hit_mine = True
            else:
                newly_revealed += self._flood_fill_reveal(nr, nc)

        self.revealed_count += newly_revealed
        self.score += newly_revealed * 10

        if hit_mine:
            self.status = GameStatus.LOST
            self.end_time = time.time()
            self._reveal_all_mines()
            return True, "BOOM! Chord hit a mine! Game Over."

        if self.revealed_count >= self.safe_cells_total:
            self._trigger_win()
            return True, "VICTORY! Chord cleared the final cells!"

        return True, f"Chord revealed {newly_revealed} cells."

    def _reveal_all_mines(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell.is_mine and not cell.is_flagged:
                    cell.is_revealed = True
                elif not cell.is_mine and cell.is_flagged:
                    cell.is_false_flag = True

    def _trigger_win(self) -> None:
        self.status = GameStatus.WON
        self.end_time = time.time()

        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell.is_mine and not cell.is_flagged:
                    cell.is_flagged = True
        self.flags_count = self.total_mines

        elapsed = self.get_elapsed_time()
        base_bonuses = {
            "Beginner": 1000,
            "Intermediate": 2500,
            "Expert": 5000,
            "PVP Race": 3000,
            "PVP 1v1": 3000,
        }
        base_bonus = base_bonuses.get(self.difficulty_name, self.rows * self.cols * 10)
        self.score += max(200, base_bonus - (elapsed * 3))
