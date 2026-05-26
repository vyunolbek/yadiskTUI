import asyncio
import os

import yadisk
from rich.style import Style
from rich.text import Text

from textual.screen import ModalScreen
from textual.widgets import Input, Label, Button, ListView, ListItem, Static
from textual.containers import Horizontal, Vertical
from textual import events

from yadisk_cli.config import (
    load_config,
    load_token,
    save_token,
    delete_token,
    list_accounts,
    get_active_account,
    set_active_account,
    get_token_path,
)


class PathInputDialog(ModalScreen):
    CSS = """
    .suggestions-list {
        height: auto;
        max-height: 10;
        border: solid $secondary;
        margin: 0 0 1 0;
        overflow-y: auto;
    }
    """

    def __init__(self, title: str, default: str = ""):
        super().__init__()
        self._dialog_title = title
        self._default = default
        self._suggestions: list[str] = []

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self._dialog_title, classes="dialog-title")
            yield Input(value=self._default, placeholder="Enter path...", id="path-input")
            yield ListView(id="path-suggestions", classes="suggestions-list")
            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self):
        self._update_suggestions(self._default)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "ok":
            self._submit()
        else:
            self.dismiss()

    def on_input_submitted(self, event: Input.Submitted):
        event.stop()
        self._submit()

    def _submit(self):
        path = self.query_one("#path-input", Input).value.strip()
        if path:
            self.dismiss(path)
        else:
            self.dismiss()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "path-input":
            self._update_suggestions(event.value)

    def on_list_view_selected(self, event: ListView.Selected):
        lst = self.query_one("#path-suggestions", ListView)
        if event.list_view is lst:
            idx = lst.index
            if idx is not None and 0 <= idx < len(self._suggestions):
                self._complete_with(idx)
            event.stop()

    def _update_suggestions(self, path: str):
        lst = self.query_one("#path-suggestions", ListView)
        lst.clear()
        self._suggestions.clear()

        if not path:
            parent = os.path.expanduser("~")
            prefix = ""
        else:
            expanded = os.path.expanduser(path)
            if os.path.isdir(expanded):
                parent = expanded.rstrip("/") or "/"
                prefix = ""
            else:
                parent = os.path.dirname(expanded) or "/"
                prefix = os.path.basename(expanded)

        if not os.path.isdir(parent):
            return

        try:
            entries = sorted(os.listdir(parent))
        except PermissionError:
            return

        matching = [e for e in entries if os.path.isdir(os.path.join(parent, e)) and e.startswith(prefix)]

        for entry in matching:
            lst.append(ListItem(Static(entry + "/")))

        self._suggestions = matching

        if matching:
            lst.index = 0

    def _complete_with(self, idx: int):
        inp = self.query_one("#path-input", Input)
        current = inp.value

        if not current:
            parent = os.path.expanduser("~")
        else:
            expanded = os.path.expanduser(current)
            if os.path.isdir(expanded):
                parent = expanded.rstrip("/") or "/"
            else:
                parent = os.path.dirname(expanded) or "/"

        new_path = os.path.join(parent, self._suggestions[idx])
        inp.value = new_path + "/"
        self._update_suggestions(inp.value)
        inp.focus()

    def on_key(self, event: events.Key):
        inp = self.query_one("#path-input", Input)
        lst = self.query_one("#path-suggestions", ListView)

        if self.focused is not inp or not self._suggestions:
            return

        if event.key == "up":
            idx = lst.index
            if idx is None or idx <= 0:
                lst.index = len(self._suggestions) - 1
            else:
                lst.index = idx - 1
            event.stop()
        elif event.key == "down":
            idx = lst.index
            if idx is None or idx >= len(self._suggestions) - 1:
                lst.index = 0
            else:
                lst.index = idx + 1
            event.stop()


class TokenInputScreen(ModalScreen):
    def __init__(self):
        super().__init__()
        cfg = load_config()
        self._client_id = cfg.get("yandex_client_id", "")

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label("Add Account", classes="dialog-title")
            if self._client_id:
                auth_url = f"https://oauth.yandex.com/authorize?response_type=token&client_id={self._client_id}&force_confirm=1"
                text = Text.assemble(
                    ("Получить OAuth-токен", Style(link=auth_url)),
                    " (откроется в браузере)\n",
                    ("Совет:", Style(bold=True)),
                    " используйте режим инкогнито, чтобы выбрать другой аккаунт",
                )
                yield Static(text, id="token-help")
            else:
                text = Text.assemble(
                    ("Зарегистрировать приложение", Style(link="https://oauth.yandex.com/client/new")),
                    " → получить client_id → настроить:\n",
                    ("yd config yandex_client_id YOUR_ID", Style(bold=True)),
                )
                yield Static(text, id="token-help")
            yield Label("Account name:")
            yield Input(id="account-name", placeholder="e.g. work, home, ...")
            yield Label("OAuth token:")
            yield Input(id="token-input", placeholder="Paste your OAuth token here...")
            yield Label("", id="token-error", classes="error-text")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Login", variant="primary", id="login")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "login":
            self._do_login()
        else:
            self.dismiss()

    def on_input_submitted(self, event: Input.Submitted):
        event.stop()
        if event.input.id == "token-input":
            self._do_login()

    def _do_login(self):
        name = self.query_one("#account-name", Input).value.strip()
        token = self.query_one("#token-input", Input).value.strip()
        error_label = self.query_one("#token-error", Label)

        if not token:
            error_label.update("Token is required.")
            return
        if not name:
            existing = list_accounts()
            base = "account"
            i = 1
            while f"{base}{i}" in existing:
                i += 1
            name = f"{base}{i}"

        if get_token_path(name).exists():
            error_label.update(f"Account '{name}' already exists.")
            return

        try:
            client = yadisk.Client(token=token)
            if not client.check_token():
                error_label.update("Token is invalid or expired.")
                return
        except Exception as e:
            error_label.update(f"Authentication failed: {e}")
            return

        save_token({"access_token": token}, name)
        set_active_account(name)
        self.dismiss(name)


class AccountListScreen(ModalScreen):
    def __init__(self):
        super().__init__()

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label("Account Management", classes="dialog-title")
            yield ListView(id="account-list")
            cfg = load_config()
            client_id = cfg.get("yandex_client_id", "")
            if client_id:
                auth_url = f"https://oauth.yandex.com/authorize?response_type=token&client_id={client_id}&force_confirm=1"
                text = Text.assemble(
                    ("Получить OAuth-токен в браузере", Style(link=auth_url)),
                    " (режим инкогнито для выбора аккаунта)",
                )
                yield Static(text, id="account-hint")
            else:
                text = Text.assemble(
                    ("Создать приложение", Style(link="https://oauth.yandex.com/client/new")),
                    " → client_id → yd config yandex_client_id YOUR_ID",
                )
                yield Static(text, id="account-hint")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Add", variant="primary", id="add")
                yield Button("Remove", id="remove")
                yield Button("Close", id="close")

    async def on_mount(self):
        await self._refresh_list()

    async def _refresh_list(self):
        list_view = self.query_one("#account-list", ListView)
        list_view.clear()
        active = get_active_account()
        for name in list_accounts():
            label = f" {name}" if name != active else f" {name} (active)"
            item = ListItem(Static(label))
            item.account_name = name
            list_view.append(item)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "add":
            self.app.push_screen(TokenInputScreen(), self._on_add_result)
        elif event.button.id == "remove":
            self._remove_selected()
        elif event.button.id == "close":
            self.dismiss(None)

    async def _on_add_result(self, result):
        if result is not None:
            self.dismiss(result)
        else:
            await self._refresh_list()

    def _remove_selected(self):
        list_view = self.query_one("#account-list", ListView)
        child = list_view.highlighted_child
        if child is None:
            return
        name = getattr(child, "account_name", "")
        if not name:
            return
        if name == get_active_account():
            self.app.notify("Cannot remove active account. Switch first.", severity="error")
            return
        delete_token(name)
        self.app.notify(f"Removed account '{name}'")
        asyncio.create_task(self._refresh_list())

    def on_list_view_selected(self, event: ListView.Selected):
        name = getattr(event.item, "account_name", "")
        if not name:
            return
        if name == get_active_account():
            self.dismiss(None)
            return
        set_active_account(name)
        self.dismiss(name)
