from textual.widgets import Static
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Group

SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]


def format_size(size: int) -> str:
    for unit in SIZE_UNITS:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class FilePreview(Static):
    def __init__(self, *args, **kwargs):
        super().__init__("", *args, **kwargs)
        self._current_item = None

    def show_item(self, item=None):
        self._current_item = item
        if item is None:
            self.update(Panel("No file selected", title="File Info"))
            return

        table = Table(show_header=False, box=None)
        table.add_column("Key", style="bold", width=12)
        table.add_column("Value")

        if item.item_type == "dir":
            table.add_row("Type", "📁 Directory")
            table.add_row("Name", item.item_name)
            table.add_row("Path", item.item_path)
            self.update(Panel(table, title="Directory Info"))
            return

        ext = item.item_name.rsplit(".", 1)[-1].upper() if "." in item.item_name else ""
        table.add_row("Type", "📄 File")
        table.add_row("Name", item.item_name)
        table.add_row("Size", format_size(item.item_size))
        if ext:
            table.add_row("Format", ext)
        table.add_row("Path", item.item_path)

        content = Group(
            table,
            Text("\n\n"),
            Text("[d] Download", style="bold green"),
            Text("\n"),
            Text("[D] Download to...", style="bold yellow"),
            Text("\n\n"),
            Text("Enter to download", style="dim"),
        )
        self.update(Panel(content, title="File Info"))

    def show_message(self, message: str):
        self.update(Panel(message, title="Status"))
