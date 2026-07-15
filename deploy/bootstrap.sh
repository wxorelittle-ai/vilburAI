#!/usr/bin/env bash
# Вильбур AI — автоматический деплой в один заход (неинтерактивно).
#
# Использование (на сервере, от root; код уже склонирован в /opt/brigadir_pro):
#   sudo DOMAIN=ваш-домен.ru EMAIL=почта@для-ssl.ru bash /opt/brigadir_pro/deploy/bootstrap.sh
#
# Делает всё: пакеты, PostgreSQL, venv, .env, миграции, статику, Gunicorn(systemd),
# Nginx и SSL (Let's Encrypt). Идемпотентно — можно запускать повторно.
set -euo pipefail

DOMAIN="${DOMAIN:?Укажите DOMAIN=ваш-домен.ru}"
EMAIL="${EMAIL:?Укажите EMAIL=почта для SSL-уведомлений}"
APP_DIR="${APP_DIR:-/opt/brigadir_pro}"
APP_USER=brigadir
DB_NAME=brigadir_pro
DB_USER=brigadir_pro

echo "==> [1/10] Системные пакеты и зависимости сборки"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    postgresql postgresql-contrib nginx certbot python3-certbot-nginx git curl openssl \
    build-essential python3-dev python3-venv python3-pip \
    libpq-dev libjpeg-dev zlib1g-dev libxml2-dev libxslt1-dev libffi-dev libssl-dev

# Предпочитаем Python 3.12 (лучшее покрытие wheel'ами), иначе системный python3
PYBIN=""
command -v python3.12 >/dev/null 2>&1 && PYBIN=$(command -v python3.12)
if [ -z "$PYBIN" ]; then
    apt-get install -y --no-install-recommends software-properties-common || true
    add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null && apt-get update -y || true
    apt-get install -y python3.12 python3.12-venv python3.12-dev 2>/dev/null || true
    command -v python3.12 >/dev/null 2>&1 && PYBIN=$(command -v python3.12)
fi
[ -z "$PYBIN" ] && PYBIN=$(command -v python3)
echo "    Python: $PYBIN ($($PYBIN --version 2>&1))"

echo "==> [2/10] Системный пользователь приложения"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"

echo "==> [3/10] PostgreSQL: база и пользователь (+ права схемы public для PG15+)"
systemctl enable --now postgresql
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME};"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER ${DB_USER};"
sudo -u postgres psql -c "ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"
# Пароль БД задаётся ТОЛЬКО при первом деплое (когда пишется .env) — см. шаг [5].
# Иначе повторный запуск сбрасывал бы пароль в БД, а .env оставался старым.

echo "==> [4/10] Виртуальное окружение и зависимости"
[ -d "$APP_DIR/venv" ] || "$PYBIN" -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip wheel
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> [5/10] .env"
if [ ! -f "$APP_DIR/.env" ]; then
    # первый запуск: задаём пароль БД и пишем совпадающий .env
    DB_PASSWORD=$(openssl rand -hex 20)
    sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"
    SECRET=$("$APP_DIR/venv/bin/python" -c "import secrets;print(secrets.token_urlsafe(50))")
    cat > "$APP_DIR/.env" <<EOF
SECRET_KEY=${SECRET}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN}
CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
DATABASE_URL=postgres://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
YOOKASSA_TEST_MODE=True
EOF
    echo "    .env создан (SECRET_KEY и пароль БД сгенерированы и синхронизированы)"
else
    echo "    .env уже существует — пароль БД и настройки не трогаю"
fi

echo "==> [6/10] Логи и права"
mkdir -p /var/log/brigadir_pro /run/brigadir_pro
chown -R "$APP_USER":www-data "$APP_DIR" /var/log/brigadir_pro

echo "==> [7/10] Миграции и статика"
# ВАЖНО: manage.py под sudo -u не всегда подхватывает .env через decouple и может
# свалиться в SQLite-фолбэк. Передаём DATABASE_URL из .env в окружение явно, чтобы
# миграции гарантированно шли в PostgreSQL (а не в локальный db.sqlite3).
set -a; . "$APP_DIR/.env"; set +a
rm -f "$APP_DIR/db.sqlite3"
sudo -u "$APP_USER" env DATABASE_URL="$DATABASE_URL" PGSSLMODE=disable "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" migrate --noinput
sudo -u "$APP_USER" env DATABASE_URL="$DATABASE_URL" PGSSLMODE=disable "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput

echo "==> [8/10] Gunicorn (systemd)"
cp "$APP_DIR/deploy/brigadir_pro.service" /etc/systemd/system/brigadir_pro.service
systemctl daemon-reload
systemctl enable brigadir_pro
systemctl restart brigadir_pro

echo "==> [9/10] Nginx (HTTP-конфиг; SSL добавит certbot)"
cp "$APP_DIR/deploy/proxy_params_brigadir" /etc/nginx/proxy_params_brigadir
cat > /etc/nginx/sites-available/brigadir_pro <<EOF
limit_req_zone \$binary_remote_addr zone=brigadir_login:10m rate=5r/m;
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    client_max_body_size 10M;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    access_log /var/log/nginx/brigadir_pro-access.log;
    error_log  /var/log/nginx/brigadir_pro-error.log;
    location /static/ { alias ${APP_DIR}/staticfiles/; expires 30d; add_header Cache-Control "public, immutable"; }
    location /media/  { alias ${APP_DIR}/media/; expires 7d; }
    location /login/ { limit_req zone=brigadir_login burst=3 nodelay; proxy_pass http://127.0.0.1:8000; include /etc/nginx/proxy_params_brigadir; }
    location / { proxy_pass http://127.0.0.1:8000; include /etc/nginx/proxy_params_brigadir; }
}
EOF
ln -sf /etc/nginx/sites-available/brigadir_pro /etc/nginx/sites-enabled/brigadir_pro
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> [10/10] SSL (Let's Encrypt)"
if certbot --nginx -d "${DOMAIN}" -d "www.${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" --redirect; then
    echo "    SSL выпущен, HTTP -> HTTPS настроен."
else
    echo "    ! SSL пока не выпущен — чаще всего потому, что DNS ещё не указывает на этот сервер."
    echo "      Проверьте A-запись ${DOMAIN} -> IP сервера и повторите:"
    echo "      certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} --agree-tos -m ${EMAIL} --redirect"
fi
systemctl restart brigadir_pro

cat <<EOF

================= ГОТОВО =================
Сайт:  https://${DOMAIN}/
Админка: https://${DOMAIN}/admin/

Осталось (по желанию):
1) Создать администратора:
   sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python ${APP_DIR}/manage.py createsuperuser
2) Ежедневный автобэкап (03:00):
   ( crontab -l 2>/dev/null; echo '0 3 * * * ${APP_DIR}/deploy/backup.sh >> /var/log/brigadir_pro/backup.log 2>&1' ) | crontab -
3) Ключи ЮKassa и модулей — впишите в ${APP_DIR}/.env и: systemctl restart brigadir_pro
=========================================
EOF
