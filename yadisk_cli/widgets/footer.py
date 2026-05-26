from textual.widgets import Label


class Footer(Label):
    def __init__(self, *args, **kwargs):
        super().__init__("", *args, **kwargs)

    def update_info(self, path: str = "/", download_dir: str = "", disk_info: str = ""):
        parts = []
        if disk_info:
            parts.append(disk_info)
        parts.append(f"Path: {path}")
        parts.append(f"DL: {download_dir}")
        self.update(" │ ".join(parts))
