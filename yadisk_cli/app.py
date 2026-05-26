import asyncio
import os
from pathlib import PurePosixPath
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, Button, Label
from textual.screen import ModalScreen

from yadisk_cli.client import get_async_client
from yadisk_cli.config import get_download_dir, set_download_dir as save_download_dir, get_active_account, set_active_account
from yadisk_cli.widgets.file_browser import FileBrowser, FileItem
from yadisk_cli.widgets.file_preview import FilePreview
from yadisk_cli.widgets.footer import Footer
from yadisk_cli.widgets.dialogs import PathInputDialog, AccountListScreen


class YadiskApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    .horizontal-panels {
        height: 1fr;
    }

    #file-browser {
        width: 2fr;
        border: solid $primary;
        min-width: 30;
    }

    #file-preview {
        width: 3fr;
        border: solid $primary;
    }

    #footer {
        height: 1;
        dock: bottom;
        background: $panel;
        color: $text;
        padding: 0 1;
    }

    #command-bar {
        height: 1;
        dock: bottom;
        background: $boost;
        color: $text;
        padding: 0 1;
        visibility: hidden;
    }

    #command-input {
        height: 1;
    }

    .dialog {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        margin: 5 8;
    }

    .dialog-title {
        text-style: bold;
        padding-bottom: 1;
    }

    .dialog-buttons {
        align: center middle;
        padding-top: 1;
    }

    .error-text {
        color: $error;
        padding: 0 1;
    }

    #token-help {
        padding: 0 0 1 0;
    }

    #account-hint {
        padding: 0 1;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+a", "accounts", "Accounts"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "download", "Download"),
        Binding("D", "download_to", "Download to..."),
        Binding("slash", "search", "Search"),
        Binding("colon", "command_mode", "Command"),
        Binding("backspace", "go_up", "Up"),
        Binding("h", "go_up", "Up"),
    ]

    def __init__(self, client, account_name: str = "", download_dir: Optional[str] = None):
        super().__init__()
        self._client = client
        self._account_name = account_name or get_active_account()
        self._selected_item: Optional[FileItem] = None
        self._download_dir = download_dir or get_download_dir()
        self._downloading = False

    def compose(self):
        with Horizontal(classes="horizontal-panels"):
            yield FileBrowser(client=self._client, id="file-browser")
            yield FilePreview(id="file-preview")
        yield Footer(id="footer")
        with Horizontal(id="command-bar"):
            yield Input(id="command-input", placeholder=":", classes="command-input")

    async def on_mount(self):
        await self._update_disk_info()

    async def on_unmount(self):
        try:
            await self._client.close()
        except Exception:
            pass

    async def _update_disk_info(self):
        try:
            info = await self._client.get_disk_info()
            total = info["total_space"]
            used = info["used_space"]
            free = total - used
            fmt = f"💾 {_fmt_size(free)} / {_fmt_size(total)}"
            self.query_one("#footer", Footer).update_info(
                path="/",
                download_dir=self._download_dir,
                disk_info=fmt,
                account_name=self._account_name,
            )
        except Exception:
            pass

    async def action_accounts(self):
        def on_account_result(result):
            if result is None:
                return
            asyncio.create_task(self._switch_account(result))

        self.push_screen(AccountListScreen(), callback=on_account_result)

    async def _switch_account(self, name: str):
        if name == self._account_name:
            return
        try:
            await self._client.close()
        except Exception:
            pass
        client = await get_async_client(name)
        if client is None:
            self.notify(f"Account '{name}' not authenticated", severity="error")
            return
        self._client = client
        self._account_name = name
        browser = self.query_one("#file-browser", FileBrowser)
        browser._client = client
        await browser.load_directory("/")
        await self._update_disk_info()
        self.notify(f"Switched to account '{name}'")

    async def on_list_view_highlighted(self, event):
        browser = self.query_one("#file-browser", FileBrowser)
        if event.list_view is not browser:
            return

        item = event.item
        if not isinstance(item, FileItem):
            return

        self._selected_item = item
        preview = self.query_one("#file-preview", FilePreview)
        preview.show_item(item)
        footer = self.query_one("#footer", Footer)
        footer.update_info(
            path=browser.current_path,
            download_dir=self._download_dir,
            account_name=self._account_name,
        )
        event.stop()

    async def on_list_view_selected(self, event):
        browser = self.query_one("#file-browser", FileBrowser)
        if event.list_view is not browser:
            return

        item = event.item
        if not isinstance(item, FileItem) or item.item_type != "dir":
            return

        await browser.load_directory(item.item_path)
        footer = self.query_one("#footer", Footer)
        footer.update_info(
            path=browser.current_path,
            download_dir=self._download_dir,
            account_name=self._account_name,
        )
        event.stop()

    async def action_download(self):
        if self._selected_item is None or self._selected_item.item_type != "file" or self._downloading:
            return

        self._downloading = True
        try:
            remote = self._selected_item.item_path
            name = self._selected_item.item_name
            local = os.path.join(self._download_dir, name)
            await self._do_download(remote, local)
        finally:
            self._downloading = False

    async def action_download_to(self):
        if self._selected_item is None or self._selected_item.item_type != "file" or self._downloading:
            return

        def on_path(path):
            if path is None:
                return
            browser = self.query_one("#file-browser", FileBrowser)
            browser.focus()
            self._downloading = True
            path = os.path.expanduser(path)
            name = self._selected_item.item_name
            local = os.path.join(path, name) if os.path.isdir(path) else path
            task = asyncio.create_task(self._do_download(self._selected_item.item_path, local))
            task.add_done_callback(lambda _: setattr(self, "_downloading", False))

        self.push_screen(PathInputDialog("Download to:", default=self._download_dir), callback=on_path)

    async def _do_download(self, remote_path: str, local_path: str):
        try:
            preview = self.query_one("#file-preview", FilePreview)
            preview.show_message(f"Downloading...\n{remote_path}\n→ {local_path}")
            os.makedirs(os.path.dirname(os.path.abspath(local_path)) or ".", exist_ok=True)
            await self._client.download(remote_path, local_path)
            preview.show_message(f"Download complete!\n{remote_path}\n→ {local_path}")
            self.notify(f"Downloaded: {local_path}")
            await asyncio.sleep(1.5)
        except Exception as e:
            self.notify(f"Download failed: {e}", severity="error")
        finally:
            if self._selected_item:
                preview = self.query_one("#file-preview", FilePreview)
                preview.show_item(self._selected_item)
            browser = self.query_one("#file-browser", FileBrowser)
            browser.focus()

    async def action_open_selected(self):
        browser = self.query_one("#file-browser", FileBrowser)
        child = browser.highlighted_child
        if isinstance(child, FileItem):
            if child.item_type == "dir":
                await browser.load_directory(child.item_path)
                footer = self.query_one("#footer", Footer)
                footer.update_info(
                    path=browser.current_path,
                    download_dir=self._download_dir,
                    account_name=self._account_name,
                )
            elif child.item_type == "file":
                self._selected_item = child
                preview = self.query_one("#file-preview", FilePreview)
                preview.show_item(child)
                await self.action_download()

    async def action_go_up(self):
        browser = self.query_one("#file-browser", FileBrowser)
        current = browser.current_path
        if current == "/":
            return
        parent = str(PurePosixPath(current).parent)
        await browser.load_directory(parent)

    async def action_refresh(self):
        browser = self.query_one("#file-browser", FileBrowser)
        await browser.refresh_current()

    async def action_search(self):
        self._enter_command("/")

    async def action_command_mode(self):
        self._enter_command(":")

    def _enter_command(self, prefix: str = ""):
        bar = self.query_one("#command-bar")
        bar.styles.visibility = "visible"
        inp = self.query_one("#command-input", Input)
        inp.value = prefix
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted):
        bar = self.query_one("#command-bar")
        bar.styles.visibility = "hidden"
        value = event.value.strip()
        self.query_one("#file-browser", FileBrowser).focus()
        asyncio.create_task(self._handle_command(value))

    async def _handle_command(self, cmd: str):
        if not cmd:
            return
        if cmd.startswith(":"):
            self._handle_internal(cmd[1:])
        elif cmd.startswith("/"):
            query = cmd[1:]
            if query:
                await self._filter_files(query)
            else:
                browser = self.query_one("#file-browser", FileBrowser)
                await browser.refresh_current()

    def _handle_internal(self, cmd: str):
        parts = cmd.split(None, 1)
        command = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if command in ("download-dir", "dd"):
            if arg:
                self._download_dir = os.path.abspath(os.path.expanduser(arg))
                save_download_dir(self._download_dir)
                self.query_one("#footer", Footer).update_info(
                    path=self.query_one("#file-browser", FileBrowser).current_path,
                    download_dir=self._download_dir,
                    account_name=self._account_name,
                )
                self.notify(f"Download dir set to: {self._download_dir}")
            else:
                self.notify(f"Current download dir: {self._download_dir}")
        elif command in ("q", "quit"):
            self.exit()
        elif command == "refresh":
            asyncio.create_task(self.action_refresh())

    async def _filter_files(self, query: str):
        browser = self.query_one("#file-browser", FileBrowser)
        for child in list(browser.children):
            if isinstance(child, FileItem):
                if child.item_name == "..":
                    child.display = True
                else:
                    child.display = query.lower() in child.item_name.lower()

    def key_escape(self):
        bar = self.query_one("#command-bar")
        if bar.styles.visibility == "visible":
            bar.styles.visibility = "hidden"
            self.query_one("#file-browser", FileBrowser).focus()
        else:
            self.exit()

    def on_input_cancelled(self):
        bar = self.query_one("#command-bar")
        bar.styles.visibility = "hidden"
        self.query_one("#file-browser", FileBrowser).focus()


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
