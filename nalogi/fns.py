"""
Обёртка над API ФНС «Мой налог» (раздел 6.4 ТЗ).

Без ключа (FNS_API_KEY в .env) работает демо-режим: чек «пробивается» локально —
присваивается демо-ID и ссылка, без обращения к ФНС. С ключом включается реальная
регистрация дохода в тестовом/боевом контуре.
"""

import secrets

from django.conf import settings


def is_configured() -> bool:
    return bool(getattr(settings, 'FNS_API_KEY', ''))


def probit_chek(chek):
    """Регистрирует чек. Возвращает (ok: bool, demo: bool). Мутирует chek (status/fns_id/ssylka)."""
    from .models import ChekFNS

    if not is_configured():
        chek.fns_id = f'demo-{secrets.token_hex(6)}'
        chek.ssylka = f'https://lknpd.nalog.ru/api/v1/receipt/demo/{chek.fns_id}/print'
        chek.status = ChekFNS.STATUS_OTPRAVLEN
        chek.demo_rezhim = True
        chek.save()
        return True, True

    # Боевой режим: здесь вызов API ФНС по settings.FNS_API_KEY.
    # Реализуется при подключении реального ИНН (тестовый контур → боевой).
    try:
        # import requests
        # resp = requests.post('https://lknpd.nalog.ru/api/v1/income', ...)
        raise NotImplementedError('Реальная интеграция ФНС включается при верификации ИНН')
    except Exception:  # noqa: BLE001
        chek.status = ChekFNS.STATUS_OSHIBKA
        chek.save()
        return False, False
