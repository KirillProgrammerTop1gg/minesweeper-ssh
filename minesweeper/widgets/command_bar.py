from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from minesweeper.game import parse_command


class CommandBar(Widget):
    DEFAULT_CSS = """
    CommandBar {
        height: 3;
        width: 100%;
        background: $surface;
        padding: 0 1;
        layout: horizontal;
    }
    CommandBar #cmd_label {
        margin: 1 1 0 0;
        text-style: bold;
        color: $accent;
    }
    CommandBar Input {
        width: 30;
        margin-right: 1;
    }
    CommandBar Button {
        min-width: 14;
        margin-right: 1;
    }
    CommandBar #feedback_label {
        margin: 1 0 0 1;
        color: $text-muted;
    }
    """

    class ExecuteCoordinate(Message):
        def __init__(self, action: str, row: int, col: int) -> None:
            super().__init__()
            self.action = action
            self.row = row
            self.col = col

    def compose(self) -> ComposeResult:
        yield Label("Coordinates:", id="cmd_label")
        yield Input(
            placeholder="e.g. B5 or F B5",
            id="cmd_input",
        )
        yield Button("Open [O]", id="btn_open", variant="primary")
        yield Button("Flag [F]", id="btn_flag", variant="warning")
        yield Label("Press Enter or button", id="feedback_label")

    def show_feedback(self, text: str, is_error: bool = False) -> None:
        lbl = self.query_one("#feedback_label", Label)
        lbl.update(f"[!] {text}" if is_error else f"[*] {text}")
        lbl.styles.color = "red" if is_error else "green"

    def focus_input(self) -> None:
        self.query_one("#cmd_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return

        try:
            action, row, col = parse_command(value)
            event.input.value = ""
            self.post_message(self.ExecuteCoordinate(action, row, col))
        except ValueError as err:
            self.show_feedback(str(err), is_error=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        input_widget = self.query_one("#cmd_input", Input)
        value = input_widget.value.strip()

        button_id = event.button.id
        action = "open" if button_id == "btn_open" else "flag"

        if value:
            try:
                _, row, col = parse_command(value)
                input_widget.value = ""
                self.post_message(self.ExecuteCoordinate(action, row, col))
            except ValueError as err:
                self.show_feedback(str(err), is_error=True)
        else:
            self.post_message(self.ExecuteCoordinate(action, -1, -1))
