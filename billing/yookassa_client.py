"""
Обёртка над ЮKassa (раздел 6.1 ТЗ).

Без реальных ключей (YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY в .env) работает
в демо-режиме: подписка активируется мгновенно локально, без обращения к
внешнему API и без реального списания денег. Это сознательное решение для
десктоп-версии и локальной разработки — как только ключи появятся в .env,
включается настоящий процессинг через ЮKassa (тестовый или боевой — управляется
YOOKASSA_TEST_MODE).

Безопасность вебхука: ЮKassa не подписывает уведомления секретом, поэтому телу
запроса верить нельзя — иначе любой, кто знает id своего платежа, отправит
поддельное «payment.succeeded» и получит платный тариф бесплатно. Защита —
двухслойная: (1) IP отправителя из официальных сетей ЮKassa, (2) главное —
подтверждение платежа встречным запросом к API по секретному ключу.
"""

import ipaddress
import uuid
from decimal import Decimal

from django.conf import settings

# Официальные сети, с которых ЮKassa шлёт уведомления (можно переопределить
# в settings.YOOKASSA_TRUSTED_IPS, если провайдер поменяет диапазоны).
SETI_YOOKASSA = [
    '185.71.76.0/27',
    '185.71.77.0/27',
    '77.75.153.0/25',
    '77.75.156.11/32',
    '77.75.156.35/32',
    '77.75.154.128/25',
    '2a02:5180::/32',
]


def is_configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


def _nastroit():
    from yookassa import Configuration
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def create_payment(brigada, tarif: str, summa, return_url: str):
    """
    Создаёт платёж. Возвращает dict: {'confirmation_url': str|None, 'yookassa_id': str, 'demo': bool}.
    В боевом режиме confirmation_url ведёт на страницу оплаты ЮKassa.
    В демо-режиме confirmation_url — None, вызывающий код должен сразу
    считать платёж успешным (см. billing/views.py).
    """
    if not is_configured():
        return {
            'confirmation_url': None,
            'yookassa_id': f'demo-{uuid.uuid4().hex[:12]}',
            'demo': True,
        }

    from yookassa import Payment

    _nastroit()
    payment = Payment.create({
        'amount': {'value': f'{summa:.2f}', 'currency': 'RUB'},
        'confirmation': {'type': 'redirect', 'return_url': return_url},
        'capture': True,
        'description': f'Вильбур AI — тариф «{tarif}» для {brigada.nazvanie}',
        'metadata': {'brigada_id': brigada.pk, 'tarif': tarif},
    }, uuid.uuid4())

    return {
        'confirmation_url': payment.confirmation.confirmation_url,
        'yookassa_id': payment.id,
        'demo': False,
    }


# --- Безопасность вебхука ------------------------------------------------------

def klientskiy_ip(request) -> str:
    """IP отправителя уведомления (общая логика — см. core.utils)."""
    from core.utils import klientskiy_ip as _ip
    return _ip(request)


def ip_iz_seti_yookassa(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    seti = getattr(settings, 'YOOKASSA_TRUSTED_IPS', None) or SETI_YOOKASSA
    for net in seti:
        try:
            if addr in ipaddress.ip_network(net):
                return True
        except ValueError:
            continue
    return False


def podtverdit_platezh(yookassa_id: str):
    """
    Главная проверка: спрашиваем у ЮKassa напрямую (GET /payments/{id} по секретному
    ключу), действительно ли платёж оплачен. Телу уведомления не доверяем.
    Возвращает dict {'status', 'paid', 'summa', 'valyuta'} или None при ошибке.
    """
    if not is_configured():
        return None
    from yookassa import Payment
    _nastroit()
    try:
        p = Payment.find_one(yookassa_id)
    except Exception:  # noqa: BLE001 — сеть/неизвестный id: считаем неподтверждённым
        return None
    if p is None:
        return None
    return {
        'status': getattr(p, 'status', None),
        'paid': bool(getattr(p, 'paid', False)),
        'summa': Decimal(str(p.amount.value)) if getattr(p, 'amount', None) else None,
        'valyuta': getattr(p.amount, 'currency', None) if getattr(p, 'amount', None) else None,
    }


def platezh_deystvitelno_oplachen(platezh) -> bool:
    """Подтверждает у ЮKassa, что платёж оплачен и сумма совпадает с нашей записью."""
    dannye = podtverdit_platezh(platezh.yookassa_id)
    if not dannye:
        return False
    if dannye['status'] != 'succeeded' or not dannye['paid']:
        return False
    if dannye['summa'] is None or dannye['summa'] != platezh.summa:
        return False
    if dannye['valyuta'] and dannye['valyuta'] != 'RUB':
        return False
    return True
