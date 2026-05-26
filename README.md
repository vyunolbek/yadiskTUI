# yadisk-cli

CLI-браузер для Яндекс.Диска с двухпанельным TUI. В отличие от официального клиента, не синхронизирует файлы автоматически — вы сами решаете, что и когда скачивать.

## Возможности

- Навигация по всем папкам Яндекс.Диска (метаданные без скачивания)
- Двухпанельный TUI: слева список файлов, справа информация о выбранном файле
- Скачивание только по запросу (клавиша `d` или `Enter`)
- Поиск/фильтр по имени (`/`)
- Командный режим (`:`)
- Настраиваемая папка для скачивания (конфиг, CLI-аргумент, смена в TUI)

## Установка

```bash
git clone <repo-url> yadisk_cli
cd yadisk_cli
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Аутентификация

### Через прямой токен (рекомендуется)

1. Зарегистрируйте приложение на https://oauth.yandex.com/client/new (платформа: Web services, redirect URI: `https://oauth.yandex.ru/verification_code`)
2. Откройте в браузере:
   ```
   https://oauth.yandex.com/authorize?response_type=token&client_id=ВАШ_CLIENT_ID
   ```
3. Разрешите доступ — браузер перенаправит на URL с токеном в фрагменте `#access_token=...`
4. Скопируйте токен:
   ```bash
   .venv/bin/yd login --token СКОПИРОВАННЫЙ_ТОКЕН
   ```

### Через Device flow

```bash
.venv/bin/yd config yandex_client_id ВАШ_CLIENT_ID
.venv/bin/yd config yandex_client_secret ВАШ_CLIENT_SECRET
.venv/bin/yd login
```

Откройте URL https://ya.ru/device, введите код — программа автоматически получит токен.

## Использование

```bash
yd                        # Запуск TUI
yd login --token <token>  # Аутентификация по токену
yd logout                 # Удалить токен
yd status                 # Показать квоту диска
yd config                 # Показать конфиг
yd config <key> <value>   # Изменить конфиг
yd --download-dir /path   # Запуск TUI с кастомной папкой скачивания
```

### Управление в TUI

| Клавиша | Действие |
|---|---|
| `↑` `↓` / `j` `k` | Навигация по списку |
| `Enter` / `l` | Войти в папку / Скачать файл |
| `←` / `h` / `Backspace` | На уровень выше |
| `d` | Скачать выбранный файл |
| `D` | Скачать с выбором пути |
| `/` | Поиск/фильтр по имени |
| `:` | Командный режим |
| `r` | Обновить текущую папку |
| `q` / `Esc` | Выход |

### Команды командного режима

| Команда | Описание |
|---|---|
| `:download-dir /path` | Сменить папку для скачивания |
| `:download-dir` | Показать текущую папку |
| `:refresh` | Обновить |
| `:q` / `:quit` | Выход |

## Конфигурация

`~/.config/yadisk_cli/config.toml`:

```toml
download_dir = "/home/user/Downloads"
yandex_client_id = "ваш_client_id"
yandex_client_secret = "ваш_client_secret"
```

## Зависимости

- Python >= 3.10
- [yadisk](https://github.com/ivknv/yadisk) — REST API Яндекс.Диска
- [textual](https://github.com/Textualize/textual) — TUI фреймворк
- [typer](https://github.com/fastapi/typer) — CLI-интерфейс
