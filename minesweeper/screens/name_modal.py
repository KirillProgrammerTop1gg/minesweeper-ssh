from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class NamePromptModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Skip", show=False),
    ]

    DEFAULT_CSS = """
    NamePromptModal {
        align: center middle;
    }
    #name_dialog {
        width: 48;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #name_title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #name_info {
        text-align: center;
        margin-bottom: 1;
    }
    #name_input {
        width: 100%;
        margin-bottom: 1;
    }
    #name_buttons {
        height: 3;
        align: center middle;
    }
    #name_buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, title: str, subtitle: str, default_name: str = "Player 1", **kwargs) -> None:
        super().__init__(**kwargs)
        self.dialog_title = title
        self.dialog_subtitle = subtitle
        self.default_name = default_name

    def compose(self) -> ComposeResult:
        with Vertical(id="name_dialog"):
            yield Label(self.dialog_title, id="name_title")
            yield Label(self.dialog_subtitle, id="name_info")
            yield Input(value=self.default_name, id="name_input")
            with Horizontal(id="name_buttons"):
                yield Button("Save Score", id="btn_save", variant="primary")
                yield Button("Skip (Esc)", id="btn_skip", variant="default")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            val = self.query_one("#name_input", Input).value.strip() or self.default_name
            self.dismiss(val)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip() or self.default_name
        self.dismiss(val)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
