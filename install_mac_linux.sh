#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Бригадир.Про — установка десктоп-версии"
echo "============================================================"
echo

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3 не найден. Установите его:"
    echo "  macOS:  brew install python@3.12"
    echo "  Linux:  sudo apt install python3 python3-venv"
    exit 1
fi

echo "Использую $($PYTHON_BIN --version)"

echo "Создаю виртуальное окружение..."
"$PYTHON_BIN" -m venv venv
source venv/bin/activate

echo "Устанавливаю зависимости (это может занять пару минут)..."
pip install --upgrade pip --quiet
pip install -r requirements.txt
pip install -r requirements-desktop.txt

# На Linux нативному окну pywebview нужен системный WebKitGTK.
# Без него приложение автоматически откроется в браузере по умолчанию —
# это не ошибка, просто чуть менее «десктопный» вид.
if [ "$(uname)" = "Linux" ]; then
    echo
    echo "Подсказка (Linux): для нативного окна приложения (не обязательно) можно"
    echo "установить: sudo apt install python3-gi gir1.2-webkit2-4.1"
    echo "Без этого приложение всё равно запустится — просто откроется в браузере."
fi

echo
echo "Установка завершена. Запускаю приложение..."
echo

python desktop/launcher.py
