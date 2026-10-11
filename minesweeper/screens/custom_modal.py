from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class CustomGameModal(ModalScreen[tuple[int, int, int] | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    CustomGameModal {
        align: center middle;
    }
    #custom_dialog {
        width: 52;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #custom_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .input_row {
        height: 3;
        margin-bottom: 1;
    }
    .input_row Label {
        width: 22;
        margin-top: 1;
    }
    .input_row Input {
        width: 24;
    }
    #buttons_row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    #buttons_row Button {
        margin: 0 1;
    }
    #error_label {
        color: red;
        text-align: center;
        margin-top: 1;
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="custom_dialog"):
            yield Label("Custom Board Settings", id="custom_title")

            with Horizontal(classes="input_row"):
                yield Label("Width (5 - 50):")
                yield Input(value="20", id="input_cols", type="integer")

            with Horizontal(classes="input_row"):
                yield Label("Height (5 - 30):")
                yield Input(value="15", id="input_rows", type="integer")

            with Horizontal(classes="input_row"):
                yield Label("Mines count:")
                yield Input(value="30", id="input_mines", type="integer")

            yield Label("", id="error_label")

            with Horizontal(id="buttons_row"):
                yield Button("Start Game", id="btn_submit", variant="primary")
                yield Button("Cancel (Esc)", id="btn_cancel", variant="default")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
            return

        focused = self.app.focused
        focused_id = focused.id if focused else None

        if event.key == "down":
            event.stop()
            if focused_id == "input_cols":
                self.query_one("#input_rows", Input).focus()
            elif focused_id == "input_rows":
                self.query_one("#input_mines", Input).focus()
            elif focused_id == "input_mines":
                self.query_one("#btn_submit", Button).focus()
            elif focused_id in ("btn_submit", "btn_cancel"):
                self.query_one("#input_cols", Input).focus()
            else:
                self.focus_next()

        elif event.key == "up":
            event.stop()
            if focused_id == "input_cols":
                self.query_one("#btn_submit", Button).focus()
            elif focused_id == "input_rows":
                self.query_one("#input_cols", Input).focus()
            elif focused_id == "input_mines":
                self.query_one("#input_rows", Input).focus()
            elif focused_id in ("btn_submit", "btn_cancel"):
                self.query_one("#input_mines", Input).focus()
            else:
                self.focus_previous()

        elif event.key in ("right", "left"):
            if focused_id == "btn_submit":
                event.stop()
                self.query_one("#btn_cancel", Button).focus()
            elif focused_id == "btn_cancel":
                event.stop()
                self.query_one("#btn_submit", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(None)
            return

        if event.button.id == "btn_submit":
            self._validate_and_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._validate_and_submit()

    def _validate_and_submit(self) -> None:
        error_lbl = self.query_one("#error_label", Label)
        try:
            cols_val = int(self.query_one("#input_cols", Input).value)
            rows_val = int(self.query_one("#input_rows", Input).value)
            mines_val = int(self.query_one("#input_mines", Input).value)
        except ValueError:
            error_lbl.update("[!] Please enter valid integers!")
            return

        if not (5 <= cols_val <= 50):
            error_lbl.update("[!] Width must be between 5 and 50!")
            return

        if not (5 <= rows_val <= 30):
            error_lbl.update("[!] Height must be between 5 and 30!")
            return

        max_mines = (cols_val * rows_val) - 9
        if not (1 <= mines_val <= max_mines):
            error_lbl.update(f"[!] Mines must be between 1 and {max_mines}!")
            return

        self.dismiss((rows_val, cols_val, mines_val))
