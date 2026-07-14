"""
Обёртка над ЮKassa (раздел 6.1 ТЗ).

Без реальных ключей (YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY в .env) работает
в демо-режиме: подписка активируется мгновенно локально, без обращения к
внешнему API и без реального списания денег. Это сознательное решение для
десктоп-версии и локальной разработки — как только ключи появятся в .env,
включается настоящий процессинг через ЮKassa (тестовый или боевой — управляется
YOOKASSA_TEST_MODE).
"""

import uuid

from django.conf import settings


def is_configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


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

    from yookassa import Configuration, Payment

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

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


def verify_webhook_event(request_body: dict) -> bool:
    """
    Проверка входящего webhook-события ЮKassa (раздел 6.1 ТЗ).
    ЮKassa не подписывает вебхуки секретом «из коробки» — рекомендованная защита:
    сверка события через повторный запрос GET /payments/{id} по секретному ключу
    аккаунта. Заглушка помечена для реализации при подключении боевых ключей.
    """
    return request_body.get('event') == 'payment.succeeded'
