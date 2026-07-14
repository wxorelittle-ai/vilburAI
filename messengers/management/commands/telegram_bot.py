"""
Telegram-бот уведомлений (Модуль F). Long-polling через Bot API.

Запуск на сервере как отдельный процесс (systemd-юнит или `python manage.py telegram_bot`).
Без TELEGRAM_BOT_TOKEN команда сообщает, что бот не настроен, и завершается.
"""

import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from messengers import telegram


class Command(BaseCommand):
    help = 'Запускает Telegram-бота уведомлений (long-polling).'

    def handle(self, *args, **options):
        if not telegram.is_configured():
            self.stdout.write(self.style.WARNING(
                'TELEGRAM_BOT_TOKEN не задан — бот работает только при настроенном токене. '
                'Добавьте ключ в .env и перезапустите.'
            ))
            return

        self.stdout.write(self.style.SUCCESS('Telegram-бот запущен (long-polling). Ctrl+C для остановки.'))
        offset = None
        base = telegram.API.format(token=settings.TELEGRAM_BOT_TOKEN, method='getUpdates')
        while True:
            try:
                params = {'timeout': 30}
                if offset is not None:
                    params['offset'] = offset
                resp = requests.get(base, params=params, timeout=40)
                data = resp.json()
                for upd in data.get('result', []):
                    offset = upd['update_id'] + 1
                    try:
                        telegram.process_update(upd)
                    except Exception as exc:  # noqa: BLE001
                        self.stderr.write(f'Ошибка обработки обновления: {exc}')
            except KeyboardInterrupt:
                self.stdout.write('Остановлено.')
                break
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f'Сбой опроса: {exc}. Повтор через 5с.')
                time.sleep(5)
