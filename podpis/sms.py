"""
Отправка СМС-кода для ПЭП (раздел 6 ТЗ).

Без ключей СМС-шлюза в .env работает демо-режим: код не отправляется реально, а
возвращается вызывающему коду для показа на экране (как демо-режим ЮKassa). С ключами
(SMS_API_KEY) включается реальная отправка через шлюз (напр. SMS.ru / Wazzup).
"""

from django.conf import settings


def is_configured() -> bool:
    return bool(getattr(settings, 'SMS_API_KEY', ''))


def otpravit_kod(telefon: str, kod: str):
    """Возвращает (demo: bool, kod_dlya_pokaza: str|None).
    В демо-режиме код возвращается для показа; в боевом — отправляется по СМС."""
    if not is_configured():
        return True, kod
    try:
        import requests
        requests.get(
            'https://sms.ru/sms/send',
            params={
                'api_id': settings.SMS_API_KEY,
                'to': telefon,
                'msg': f'Бригадир.Про: код подписания {kod}',
                'json': 1,
            },
            timeout=15,
        )
    except Exception:  # noqa: BLE001 — не роняем подписание из-за сбоя шлюза
        return True, kod
    return False, None
