#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/yadisk-cli"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_NAME="yd"

PYTHON=""
for cmd in python3 python python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Ошибка: Python не найден. Установите Python >= 3.10."
    exit 1
fi

PYVER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
IFS=. read -r major minor <<< "$PYVER"
if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 10 ]; }; then
    echo "Ошибка: требуется Python >= 3.10 (найден $PYTHON $PYVER)"
    exit 1
fi

echo ">> Создание виртуального окружения в $VENV_DIR"
mkdir -p "$INSTALL_DIR"
"$PYTHON" -m venv "$VENV_DIR"

echo ">> Установка зависимостей и пакета"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR"

mkdir -p "$BIN_DIR"
WRAPPER="$BIN_DIR/$APP_NAME"

echo ">> Установка исполняемого файла в $WRAPPER"
cat > "$WRAPPER" <<'WRAPPER_EOF'
#!/usr/bin/env bash
VENV="$(dirname "$(dirname "$(readlink -f "$0")")")/share/yadisk-cli/venv"
exec "$VENV/bin/yd" "$@"
WRAPPER_EOF
chmod +x "$WRAPPER"

echo ""
echo "Установка завершена!"
echo "Убедитесь, что $BIN_DIR добавлен в ваш PATH."
echo "Запускайте: yd"
