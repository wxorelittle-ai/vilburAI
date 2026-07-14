"""
Конфигурация Gunicorn для продакшена (раздел 9 / Этап 6 ТЗ).
Запуск: gunicorn -c deploy/gunicorn.conf.py config.wsgi:application
"""

import multiprocessing
import os

bind = '127.0.0.1:8000'  # Nginx проксирует сюда; наружу порт не открываем
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
timeout = 60
graceful_timeout = 30
keepalive = 5

accesslog = '/var/log/brigadir_pro/gunicorn-access.log'
errorlog = '/var/log/brigadir_pro/gunicorn-error.log'
loglevel = 'info'

pidfile = '/run/brigadir_pro/gunicorn.pid'

# Перезапуск воркеров после N запросов — защита от постепенных утечек памяти
max_requests = 1000
max_requests_jitter = 50

raw_env = [
    f"DJANGO_SETTINGS_MODULE={os.environ.get('DJANGO_SETTINGS_MODULE', 'config.settings')}",
]
