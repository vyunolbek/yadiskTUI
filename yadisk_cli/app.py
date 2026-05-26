import asyncio
import os
from pathlib import PurePosixPath
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, Button, Label
from textual.screen import ModalScreen

from yadisk_cli.client import get_async_client, download_item_with_progress
from yadisk_cli.progress import TransferTracker, DownloadCancelled
from yadisk_cli.config import get_download_dir, set_download_dir as save_download_dir, get_active_account, set_active_account
from yadisk_cli.update import get_current_version, check_latest_version, is_newer, do_update
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
        Binding("u", "update", "Update"),
    ]

    def __init__(self, client, account_name: str = "", download_dir: Optional[str] = None):
        super().__init__()
        self._client = client
        self._account_name = account_name or get_active_account()
        self._selected_item: Optional[FileItem] = None
        self._download_dir = download_dir or get_download_dir()
        self._downloading = False
        self._dl_tracker = TransferTracker()
        self._dl_task = None
        self._dl_progress_timer = None
        self._dl_local_path = ""
        self._dl_remote_path = ""

    def compose(self):
        with Horizontal(classes="horizontal-panels"):
            yield FileBrowser(client=self._client, id="file-browser")
            yield FilePreview(id="file-preview")
        yield Footer(id="footer")
        with Horizontal(id="command-bar"):
            yield Input(id="command-input", placeholder=":", classes="command-input")

    async def on_mount(self):
        await self._update_disk_info()
        asyncio.create_task(self._check_update())

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
        if self._selected_item is None or self._downloading:
            return
        local = os.path.join(self._download_dir, self._selected_item.item_name)
        self._start_download(self._selected_item.item_path, local)

    async def action_download_to(self):
        if self._selected_item is None or self._downloading:
            return

        def on_path(path):
            if path is None:
                return
            self.query_one("#file-browser", FileBrowser).focus()
            path = os.path.expanduser(path)
            name = self._selected_item.item_name
            local = os.path.join(path, name) if os.path.isdir(path) else path
            self._start_download(self._selected_item.item_path, local)

        self.push_screen(PathInputDialog("Download to:", default=self._download_dir), callback=on_path)

    def _start_download(self, remote_path: str, local_path: str):
        preview = self.query_one("#file-preview", FilePreview)
        preview.show_message(f"Starting download...\n{remote_path}\n→ {local_path}")
        self._downloading = True
        self._dl_remote_path = remote_path
        self._dl_local_path = local_path
        self._dl_tracker = TransferTracker()
        self._dl_task = asyncio.create_task(
            download_item_with_progress(self._client, remote_path, local_path, self._selected_item.item_type, self._dl_tracker)
        )
        self._dl_task.add_done_callback(self._on_download_done)
        self._dl_progress_timer = self.set_interval(0.3, self._update_progress)

    def _update_progress(self):
        if self._dl_tracker.active:
            lines = self._dl_tracker.status_lines()
            self.query_one("#file-preview", FilePreview).show_message("\n".join(lines))

    def _on_download_done(self, task):
        if self._dl_progress_timer:
            self._dl_progress_timer.stop()
            self._dl_progress_timer = None
        try:
            task.result()
        except (asyncio.CancelledError, DownloadCancelled):
            pass
        except Exception as exc:
            self.notify(f"Download failed: {exc}", severity="error")
            if self._selected_item:
                self.query_one("#file-preview", FilePreview).show_item(self._selected_item)
            self.query_one("#file-browser", FileBrowser).focus()
            self._downloading = False
            self._dl_task = None
            return
        preview = self.query_one("#file-preview", FilePreview)
        if self._dl_tracker.cancelled:
            preview.show_message("Download cancelled!")
            self.notify("Download cancelled")
            try:
                os.remove(self._dl_local_path)
            except OSError:
                pass
        else:
            preview.show_message(f"Download complete!\n{self._dl_remote_path}\n→ {self._dl_local_path}")
            self.notify(f"Downloaded: {self._dl_local_path}")
        if self._selected_item:
            preview = self.query_one("#file-preview", FilePreview)
            preview.show_item(self._selected_item)
        self.query_one("#file-browser", FileBrowser).focus()
        self._downloading = False
        self._dl_task = None

    async def _check_update(self):
        try:
            latest = await asyncio.to_thread(check_latest_version)
            if latest:
                current = get_current_version()
                if is_newer(latest, current):
                    self.notify(
                        f"Доступно обновление: {latest} (текущая: {current}). Нажми U для обновления",
                        timeout=10,
                    )
        except Exception:
            pass

    async def action_update(self):
        self.notify("Проверка обновлений...")
        latest = await asyncio.to_thread(check_latest_version)
        if latest:
            current = get_current_version()
            if not is_newer(latest, current):
                self.notify(f"Уже последняя версия ({current})")
                return
            self.notify(f"Обновление до {latest}...")

        result = await asyncio.to_thread(do_update)
        self.notify(result)

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
        if self._dl_tracker.active or self._downloading:
            self._dl_tracker.cancel()
            self.notify("Cancelling download...")
            return
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
