#!/usr/bin/env bash
set -e

if [ ! -f venv/bin/activate ]; then
    echo "Похоже, приложение ещё не установлено."
    echo "Запустите сначала: ./install_mac_linux.sh"
    exit 1
fi

source venv/bin/activate
python desktop/launcher.py
