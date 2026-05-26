from textual.screen import ModalScreen
from textual.widgets import Input, Label, Button
from textual.containers import Horizontal, Vertical


class PathInputDialog(ModalScreen):
    def __init__(self, title: str, default: str = ""):
        super().__init__()
        self._dialog_title = title
        self._default = default

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self._dialog_title, classes="dialog-title")
            yield Input(value=self._default, placeholder="Enter path...")
            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "ok":
            self._submit()
        else:
            self.dismiss()

    def on_input_submitted(self, event: Input.Submitted):
        event.stop()
        self._submit()

    def _submit(self):
        path = self.query_one(Input).value.strip()
        if path:
            self.dismiss(path)
        else:
            self.dismiss()
