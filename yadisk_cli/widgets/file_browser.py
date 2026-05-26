from pathlib import PurePosixPath

from textual.widgets import ListView, ListItem, Static, Label
from textual.reactive import reactive
from rich.text import Text

ITEM_TYPES = {"dir": "📁", "file": "📄"}

SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]

KNOWN_SCHEMAS = ("disk:", "trash:", "app:", "photounlim:")


def clean_path(path: str) -> str:
    for scheme in KNOWN_SCHEMAS:
        if path.startswith(scheme):
            return path[len(scheme):]
    return path


def format_size(size: int) -> str:
    for unit in SIZE_UNITS:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class FileItem(ListItem):
    def __init__(self, name: str, item_type: str, size: int = 0, path: str = ""):
        self.item_name = name
        self.item_type = item_type
        self.item_size = size
        self.item_path = clean_path(path)
        icon = ITEM_TYPES.get(item_type, "📄")
        size_text = f" {format_size(size)}" if item_type == "file" else ""
        label = Text.assemble(f" {icon} ", (name, "bold"), (size_text, "dim"))
        super().__init__(Static(label, markup=False))


class FileBrowser(ListView):
    current_path = reactive("/")

    def __init__(self, client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = client
        self._load_id = 0

    async def on_mount(self):
        await self.load_directory("/")

    async def load_directory(self, path: str):
        path = clean_path(path)
        self._load_id += 1
        load_id = self._load_id
        self.clear()
        self.current_path = path

        if path != "/":
            parent = str(PurePosixPath(path).parent)
            self.append(FileItem("..", "dir", path=parent))

        try:
            items = []
            async for item in self._client.listdir(path):
                if self._load_id != load_id:
                    return
                items.append(item)

            items.sort(key=lambda x: (x.type != "dir", x.name.lower()))

            for item in items:
                if self._load_id != load_id:
                    return
                self.append(FileItem(
                    name=item.name,
                    item_type=item.type,
                    size=getattr(item, "size", 0),
                    path=item.path,
                ))
        except Exception as e:
            if self._load_id == load_id:
                self.append(ListItem(Static(f"Error: {e}")))

    async def refresh_current(self):
        await self.load_directory(self.current_path)
