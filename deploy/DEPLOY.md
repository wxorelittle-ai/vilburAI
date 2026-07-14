# Деплой Бригадир.Про на продакшен-сервер

Соответствует Этапу 6 дорожной карты ТЗ («Деплой + Запуск») и стеку из раздела 9:
Yandex Cloud / Timeweb, Ubuntu 22.04 LTS, PostgreSQL 15+, Gunicorn + Nginx.

## 1. Требования к серверу

- Ubuntu 22.04 LTS
- Минимум 1 vCPU / 2 ГБ RAM (для старта достаточно; расти по нагрузке)
- Домен, указывающий A-записью на IP сервера
- **Хостинг только в РФ** (Yandex Cloud / Timeweb) — требование раздела 16 ТЗ по 152-ФЗ;
  Oracle Cloud, AWS, Google Cloud исключены

## 2. Быстрый старт (автоматический скрипт)

```bash
# На сервере, от root:
git clone <repo-url> /tmp/brigadir_pro_src
cd /tmp/brigadir_pro_src
sudo ./deploy/setup_server.sh
```

Скрипт `deploy/setup_server.sh` последовательно:
1. Ставит системные пакеты (Python 3.12, PostgreSQL, Nginx, certbot)
2. Создаёт системного пользователя `brigadir` (без права логина)
3. Создаёт базу данных PostgreSQL и пользователя БД со случайным паролем
4. Просит скопировать код проекта в `/opt/brigadir_pro`
5. Ставит виртуальное окружение и зависимости
6. Создаёт `.env` с автосгенерированным `SECRET_KEY` и строкой подключения к БД
7. Применяет миграции и собирает статику
8. Регистрирует и запускает systemd-сервис Gunicorn
9. Настраивает Nginx (без SSL — сертификат выпускается отдельно)

После скрипта выполните вручную:

```bash
# Домен в конфиге Nginx
sudo nano /etc/nginx/sites-available/brigadir_pro   # поправить server_name

# SSL-сертификат (Let's Encrypt)
sudo certbot --nginx -d ваш-домен.ru -d www.ваш-домен.ru

# Администратор
sudo -u brigadir /opt/brigadir_pro/venv/bin/python /opt/brigadir_pro/manage.py createsuperuser
```

## 3. Ручная установка (если нужен контроль над каждым шагом)

<details>
<summary>Развернуть пошаговую инструкцию</summary>

### 3.1. Системные пакеты

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql postgresql-contrib nginx certbot python3-certbot-nginx git
```

### 3.2. PostgreSQL

```bash
sudo -u postgres psql
CREATE DATABASE brigadir_pro;
CREATE USER brigadir_pro WITH PASSWORD 'сложный-пароль';
ALTER ROLE brigadir_pro SET client_encoding TO 'utf8';
GRANT ALL PRIVILEGES ON DATABASE brigadir_pro TO brigadir_pro;
-- PostgreSQL 15+: иначе миграции упадут с "permission denied for schema public"
ALTER DATABASE brigadir_pro OWNER TO brigadir_pro;
\c brigadir_pro
GRANT ALL ON SCHEMA public TO brigadir_pro;
\q
```

### 3.3. Код и окружение

```bash
sudo mkdir -p /opt/brigadir_pro
sudo chown $USER /opt/brigadir_pro
git clone <repo-url> /opt/brigadir_pro
cd /opt/brigadir_pro
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3.4. .env

```bash
cp .env.example .env
nano .env
```

Обязательно заполнить:
- `SECRET_KEY` — случайная строка (`python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- `DEBUG=False`
- `ALLOWED_HOSTS=ваш-домен.ru,www.ваш-домен.ru`
- `DATABASE_URL=postgres://brigadir_pro:пароль@127.0.0.1:5432/brigadir_pro`
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` — из личного кабинета ЮKassa (тестовые сначала!)

### 3.5. Миграции и статика

```bash
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py createsuperuser
```

### 3.6. Gunicorn как systemd-сервис

```bash
sudo mkdir -p /var/log/brigadir_pro
sudo cp deploy/brigadir_pro.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now brigadir_pro
sudo systemctl status brigadir_pro
```

### 3.7. Nginx + SSL

```bash
sudo cp deploy/proxy_params_brigadir /etc/nginx/proxy_params_brigadir
sudo cp deploy/nginx.conf /etc/nginx/sites-available/brigadir_pro
sudo nano /etc/nginx/sites-available/brigadir_pro   # поправить server_name на свой домен
sudo ln -s /etc/nginx/sites-available/brigadir_pro /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d ваш-домен.ru -d www.ваш-домен.ru
```

</details>

## 4. Обновление приложения (последующие релизы)

```bash
sudo -u brigadir /opt/brigadir_pro/deploy/deploy.sh
```

Скрипт подтягивает код, ставит зависимости, применяет миграции, собирает статику,
запускает `manage.py check --deploy` и перезапускает Gunicorn.

## 5. Бэкапы (обязательное требование, раздел 8 ТЗ)

```bash
sudo crontab -e
# добавить строку:
0 3 * * * /opt/brigadir_pro/deploy/backup.sh >> /var/log/brigadir_pro/backup.log 2>&1
```

`deploy/backup.sh` ежедневно в 03:00 создаёт сжатый дамп PostgreSQL и архив папки
`media/` (логотипы, PDF документов и смет) в `/var/backups/brigadir_pro/`, хранит
последние 14 дней и удаляет более старые копии.

**Восстановление из бэкапа:**

```bash
gunzip -c /var/backups/brigadir_pro/brigadir_pro_ДАТА.sql.gz | psql -U brigadir_pro -h 127.0.0.1 brigadir_pro
tar -xzf /var/backups/brigadir_pro/media_ДАТА.tar.gz -C /opt/brigadir_pro/
```

## 6. Мониторинг (раздел 10 ТЗ, Этап 6)

Настройте [UptimeRobot](https://uptimerobot.com) (или аналог) — HTTP(S)-монитор на
`https://ваш-домен.ru/`, интервал проверки 5 минут, уведомления на email/Telegram
при недоступности.

Дополнительно на сервере полезно смотреть:

```bash
sudo systemctl status brigadir_pro          # статус Gunicorn
sudo journalctl -u brigadir_pro -f          # логи в реальном времени
tail -f /var/log/brigadir_pro/gunicorn-error.log
tail -f /var/log/nginx/brigadir_pro-error.log
```

## 7. Чек-лист перед публичным запуском

Соответствует разделу 10 ТЗ («Критерий готовности к запуску»):

- [ ] Регистрация + создание договора + скачивание PDF работает и укладывается в 3 минуты с телефона
- [ ] `DEBUG=False`, `SECRET_KEY` уникален и не в git
- [ ] SSL включён, HTTP редиректит на HTTPS
- [ ] `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` указывают ровно на боевой домен
- [ ] ЮKassa переключена с тестового режима на боевой (`YOOKASSA_TEST_MODE=False`)
    после проверки тестовых платежей
- [ ] Автобэкап настроен и хотя бы раз проверено восстановление из копии
- [ ] Мониторинг доступности подключён
- [ ] Тариф «Старт» даёт реальную ценность (1 договор), но ограничен водяным знаком
