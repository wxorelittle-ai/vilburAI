"""
Telegram-бот уведомлений (раздел 6.6 ТЗ).

Без TELEGRAM_BOT_TOKEN — демо-режим (уведомления не уходят). С токеном — реальная
отправка через Bot API и обработка команд ботом (см. management-команду telegram_bot):
/start <код> — привязка, /dokumenty /raschet /smeta /nalogi — быстрые сводки.
"""

from django.conf import settings

API = 'https://api.telegram.org/bot{token}/{method}'


def is_configured() -> bool:
    return bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', ''))


def bot_username() -> str:
    return getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'wilbur_ai_bot'


def _call(method, payload):
    import requests
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    return requests.post(url, json=payload, timeout=20)


def send_message(chat_id, text):
    if not is_configured():
        return False
    try:
        _call('sendMessage', {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'})
        return True
    except Exception:  # noqa: BLE001
        return False


def notify_brigada(brigada, text):
    """Отправляет уведомление привязанной бригаде (если Telegram подключён)."""
    tg = getattr(brigada, 'telegram', None)
    if tg and tg.svyazan and tg.telegram_id:
        return send_message(tg.telegram_id, text)
    return False


def _svodka(brigada, komanda):
    from documents.models import Dokument
    from calculator.models import Raschet
    from smety.models import Smeta
    from nalogi.models import NalogOtchet
    if komanda == '/dokumenty':
        n = Dokument.objects.filter(brigada=brigada).count()
        return f'📄 Документов создано: <b>{n}</b>'
    if komanda == '/raschet':
        n = Raschet.objects.filter(brigada=brigada).count()
        return f'🧮 Расчётов себестоимости: <b>{n}</b>'
    if komanda == '/smeta':
        n = Smeta.objects.filter(brigada=brigada).count()
        return f'📋 Смет: <b>{n}</b>'
    if komanda == '/nalogi':
        sv = NalogOtchet.svodka_tekushchaya(brigada)
        return f'💰 Доход за месяц: <b>{sv["dohod"]} ₽</b>\nНалог 4%: {sv["nalog_4"]} ₽ · 6%: {sv["nalog_6"]} ₽'
    return None


def process_update(update: dict):
    """Обрабатывает одно обновление Telegram (вызывается из management-команды)."""
    from .models import TelegramUser

    msg = update.get('message') or {}
    chat = msg.get('chat') or {}
    chat_id = chat.get('id')
    text = (msg.get('text') or '').strip()
    if not chat_id or not text:
        return

    if text.startswith('/start'):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ''
        tg = TelegramUser.objects.filter(connect_code=code).first() if code else None
        if tg:
            tg.telegram_id = chat_id
            tg.username = chat.get('username', '')
            tg.status = TelegramUser.STATUS_SVYAZAN
            tg.save()
            send_message(chat_id, f'✅ Telegram привязан к «{tg.brigada.nazvanie}». '
                                  f'Команды: /dokumenty /raschet /smeta /nalogi')
        else:
            send_message(chat_id, 'Чтобы привязать аккаунт, откройте в Вильбур AI раздел '
                                  '«Мессенджеры» и перейдите по кнопке подключения Telegram.')
        return

    tg = TelegramUser.objects.filter(telegram_id=chat_id, status=TelegramUser.STATUS_SVYAZAN).first()
    if not tg:
        send_message(chat_id, 'Аккаунт не привязан. Откройте раздел «Мессенджеры» в Вильбур AI.')
        return

    otvet = _svodka(tg.brigada, text.split('@')[0])
    send_message(chat_id, otvet or 'Команды: /dokumenty /raschet /smeta /nalogi')
