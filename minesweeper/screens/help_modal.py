from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown

HELP_TEXT = """
# Minesweeper - Controls & Game Modes

### Movement (Pacman Style):
* **Arrow keys (Up, Down, Left, Right)** or **WASD**.
* **Pacman wrap-around**: reaching any edge of the board wraps the cursor to the opposite side.

---

### Actions on Selected Cell:
* **`O`**, **`Enter`** or **`Space`** — Reveal cell (first click is always safe!).
* **`F`** — Place or remove flag (F).
* **`C`** — Chord (if flags around a number match its value, reveals all remaining neighbors).
* **Mouse**: Left-click to reveal, Right-click (or Shift+click) to flag.

---

### Game Modes:
1. **Beginner**: 9x9, 10 mines
2. **Intermediate**: 16x16, 40 mines
3. **Expert**: 16x30, 99 mines
4. **Custom**: configurable width, height, and mine count
5. **PVP Race (Identical Seeded Map)**:
   * Both players race concurrently on the **exact same minefield layout**!
   * No turn waiting: play in real time while tracking opponent live score, time, and status.
   * **30s Inactivity Timeout**: Taking no action for 30 seconds triggers an automatic Game Over.
   * **Boom = Elimination**: Click a mine and your run detonates. First-click relocation protects against move-1 deaths.
   * **Scoring**: Safe cells (+combo), accurate flags (+25), misflag penalty (-10), and clear speed bonus.
   * Higher total score wins (tiebroken by faster time). Winner claims rank on the leaderboard!

---

### Leaderboard:
* Press **`L`** anytime to view the top singleplayer scores and PVP match records.
* Winning games automatically prompts you to record your name in the Hall of Fame.

---

### Coordinates:
* Columns: **A -> Z, AA -> AD**, Rows: **1 -> N**.
* Input bar: enter `B5` (to open) or `F B5` (to flag). Focus with **`/`**, return with **`Esc`**.
"""


class HelpModal(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    #help_dialog {
        width: 76;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #help_scroll {
        height: 1fr;
    }
    #btn_close_help {
        margin-top: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help_dialog"):
            with ScrollableContainer(id="help_scroll"):
                yield Markdown(HELP_TEXT)
            yield Button("Close Help (Esc)", id="btn_close_help", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key in ("escape", "q", "h"):
            self.dismiss(None)
