#!/usr/bin/env bash
# Обновление приложения на сервере (раздел 8 ТЗ — «ежедневный автоматический бэкап»
# следует запускать отдельно от деплоя, см. deploy/backup.sh).
#
# Использование (от пользователя приложения или через sudo -u brigadir):
#   ./deploy/deploy.sh

set -euo pipefail

APP_DIR="/opt/brigadir_pro"
cd "$APP_DIR"

echo "=== Обновление кода ==="
git pull

echo "=== Установка зависимостей ==="
"$APP_DIR/venv/bin/pip" install -r requirements.txt

echo "=== Миграции ==="
"$APP_DIR/venv/bin/python" manage.py migrate --noinput

echo "=== Сборка статики ==="
"$APP_DIR/venv/bin/python" manage.py collectstatic --noinput

echo "=== Проверка конфигурации ==="
"$APP_DIR/venv/bin/python" manage.py check --deploy

echo "=== Перезапуск Gunicorn ==="
sudo systemctl restart brigadir_pro

echo "=== Готово. Статус сервиса: ==="
sudo systemctl status brigadir_pro --no-pager -l | head -10
