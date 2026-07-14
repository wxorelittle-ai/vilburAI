# Бригадир.Про — Docker-образ для быстрого локального запуска.
#
# Это НЕ продакшен-конфигурация (для боевого сервера см. deploy/DEPLOY.md —
# там Gunicorn + Nginx + PostgreSQL). Здесь цель — просто поднять приложение
# одной командой на любом компьютере с Docker, в обход проблем с pip/прокси
# на хост-системе (сборка идёт внутри изолированной Linux-среды Docker).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh \
    && mkdir -p /app/media /app/data

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
