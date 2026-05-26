from textual.widgets import Static
from textual.containers import Vertical
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


class FilePreview(Vertical):
    CSS = """
    #preview-info {
        height: 1fr;
    }

    #downloads-container {
        dock: bottom;
        height: auto;
        max-height: 50%;
        overflow: auto;
    }
    """

    def compose(self):
        yield Static(id="preview-info")
        yield Vertical(id="downloads-container")

    def on_mount(self):
        self.query_one("#preview-info", Static).update(Panel("No file selected", title="File Info"))

    def show_item(self, item=None):
        info_widget = self.query_one("#preview-info", Static)
        if item is None:
            info_widget.update(Panel("No file selected", title="File Info"))
            return

        table = Table(show_header=False, box=None)
        table.add_column("Key", style="bold", width=12)
        table.add_column("Value")

        if item.item_type == "dir":
            table.add_row("Type", "📁 Directory")
            table.add_row("Name", item.item_name)
            table.add_row("Path", item.item_path)
            content = Group(
                table,
                Text("\n\n"),
                Text("[d] Download directory", style="bold green"),
                Text("\n"),
                Text("[D] Download to...", style="bold yellow"),
            )
            info_widget.update(Panel(content, title="Directory Info"))
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
        info_widget.update(Panel(content, title="File Info"))

    def add_download(self, dl_id: str, text: str):
        container = self.query_one("#downloads-container", Vertical)
        widget = Static("", id=dl_id)
        container.mount(widget)
        self.update_download(dl_id, text)

    def update_download(self, dl_id: str, text: str):
        widget = self.query_one(f"#{dl_id}", Static)
        widget.update(Panel(text, title="Download"))

    def remove_download(self, dl_id: str):
        try:
            widget = self.query_one(f"#{dl_id}", Static)
            widget.remove()
        except Exception:
            pass
