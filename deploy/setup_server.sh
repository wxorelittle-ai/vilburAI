#!/usr/bin/env bash
# Первичная настройка сервера под Бригадир.Про (Ubuntu 22.04 LTS, раздел 9 ТЗ).
# Запускать от root или через sudo. Проверяйте каждый шаг перед продакшен-использованием —
# скрипт задаёт разумные дефолты, но пароли БД и домен нужно поправить под себя.
#
# Использование: sudo ./deploy/setup_server.sh

set -euo pipefail

APP_DIR="/opt/brigadir_pro"
APP_USER="brigadir"
DB_NAME="brigadir_pro"
DB_USER="brigadir_pro"

echo "=== 1. Системные пакеты ==="
apt update
apt install -y python3.12 python3.12-venv python3-pip \
    postgresql postgresql-contrib \
    nginx certbot python3-certbot-nginx \
    git curl

echo "=== 2. Пользователь для приложения (без домашнего логина) ==="
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "=== 3. PostgreSQL: база и пользователь ==="
DB_PASSWORD=$(openssl rand -base64 24)
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME};" || echo "База уже существует — пропускаю"
sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" || echo "Пользователь БД уже существует — пропускаю"
sudo -u postgres psql -c "ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
# PostgreSQL 15+: по умолчанию непривилегированный пользователь не может писать в
# схему public — без этого падают миграции («permission denied for schema public»).
sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"

echo "=== 4. Код приложения ==="
mkdir -p "$APP_DIR"
echo "Скопируйте содержимое проекта в ${APP_DIR} (git clone или rsync), затем нажмите Enter."
read -r -p ""

echo "=== 5. Виртуальное окружение и зависимости ==="
python3.12 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "=== 6. .env ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    SECRET_KEY=$("$APP_DIR/venv/bin/python" -c "import secrets; print(secrets.token_urlsafe(50))")
    sed -i "s#SECRET_KEY=.*#SECRET_KEY=${SECRET_KEY}#" "$APP_DIR/.env"
    sed -i "s#DEBUG=.*#DEBUG=False#" "$APP_DIR/.env"
    sed -i "s#DATABASE_URL=.*#DATABASE_URL=postgres://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}#" "$APP_DIR/.env"
    echo "Создан .env — не забудьте вписать домен в ALLOWED_HOSTS и ключи ЮKassa."
fi

echo "=== 7. Логи и runtime-директории ==="
mkdir -p /var/log/brigadir_pro /run/brigadir_pro
chown -R "$APP_USER":www-data "$APP_DIR" /var/log/brigadir_pro /run/brigadir_pro

echo "=== 8. Миграции и статика ==="
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" migrate --noinput
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput

echo "=== 9. systemd-сервис Gunicorn ==="
cp "$APP_DIR/deploy/brigadir_pro.service" /etc/systemd/system/brigadir_pro.service
systemctl daemon-reload
systemctl enable --now brigadir_pro

echo "=== 10. Nginx ==="
cp "$APP_DIR/deploy/proxy_params_brigadir" /etc/nginx/proxy_params_brigadir
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/brigadir_pro
ln -sf /etc/nginx/sites-available/brigadir_pro /etc/nginx/sites-enabled/brigadir_pro
nginx -t && systemctl reload nginx

echo "=== Готово ==="
echo "Осталось:"
echo "1) Указать домен в /etc/nginx/sites-available/brigadir_pro (server_name)"
echo "2) Выпустить SSL: sudo certbot --nginx -d ваш-домен.ru"
echo "3) Создать суперпользователя: sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python ${APP_DIR}/manage.py createsuperuser"
echo "4) Настроить мониторинг (UptimeRobot) на https://ваш-домен.ru/"
echo "5) Настроить ежедневный бэкап БД (см. deploy/backup.sh)"
