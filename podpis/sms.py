"""
Отправка СМС-кода для ПЭП (раздел 6 ТЗ).

Без ключей СМС-шлюза в .env работает демо-режим: код не отправляется реально, а
возвращается вызывающему коду для показа на экране (как демо-режим ЮKassa).
С ключом (SMS_API_KEY) включается реальная отправка через шлюз SMS.ru.

Безопасность: в БОЕВОМ режиме код не возвращается никогда, даже если шлюз упал.
Иначе подписать документ смог бы любой, у кого есть ссылка: достаточно дождаться
сбоя сети — и код появился бы прямо на странице, в обход владельца телефона.
"""

from django.conf import settings

DEMO = 'demo'          # шлюз не настроен — код показываем на экране
OTPRAVLENO = 'sent'    # код ушёл по СМС
OSHIBKA = 'error'      # боевой режим, но отправить не удалось — код НЕ раскрываем


def is_configured() -> bool:
    return bool(getattr(settings, 'SMS_API_KEY', ''))


def otpravit_kod(telefon: str, kod: str):
    """Возвращает (status, kod_dlya_pokaza).
    kod_dlya_pokaza не None только в демо-режиме."""
    if not is_configured():
        return DEMO, kod

    try:
        import requests
        r = requests.get(
            'https://sms.ru/sms/send',
            params={
                'api_id': settings.SMS_API_KEY,
                'to': telefon,
                'msg': f'Вильбур AI: код подписания {kod}',
                'json': 1,
            },
            timeout=15,
        )
        r.raise_for_status()
        # Шлюз отвечает 200 даже на логическую ошибку — проверяем тело ответа,
        # иначе отрапортуем «отправлено», когда ничего не ушло.
        if (r.json() or {}).get('status') != 'OK':
            return OSHIBKA, None
    except Exception:  # noqa: BLE001 — сеть/формат ответа: считаем неотправленным
        return OSHIBKA, None

    return OTPRAVLENO, None
