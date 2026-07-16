import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import yookassa_client
from .models import Platezh

logger = logging.getLogger(__name__)

PLATNYE_TARIFY = ['samozanyaty', 'brigadir', 'pro']


@login_required
def plans(request):
    """Страница тарифов с кнопками апгрейда (раздел 5 ТЗ)."""
    brigada = request.user.brigada
    tarify = []
    for kod, conf in settings.TARIFF_LIMITS.items():
        tarify.append({
            'kod': kod,
            'label': conf['label'],
            'price': conf['price'],
            'dokumenty': conf['dokumenty'],
            'raschety': conf['raschety'],
            'smety': conf['smety'],
            'is_current': kod == brigada.effective_tarif,
            'is_platny': kod in PLATNYE_TARIFY,
        })
    return render(request, 'billing/plans.html', {
        'tarify': tarify,
        'brigada': brigada,
        'demo_rezhim': not yookassa_client.is_configured(),
    })


@login_required
def upgrade(request, tarif):
    """
    Оформление подписки. Без реальных ключей ЮKassa (см. billing/yookassa_client.py)
    работает в демо-режиме — подписка активируется мгновенно, без реального платежа.
    """
    if tarif not in PLATNYE_TARIFY:
        messages.error(request, 'Неизвестный тариф.')
        return redirect('billing:plans')

    brigada = request.user.brigada
    conf = settings.TARIFF_LIMITS[tarif]
    summa = Decimal(conf['price'])

    return_url = request.build_absolute_uri(reverse('billing:success'))
    result = yookassa_client.create_payment(brigada, tarif, summa, return_url)

    platezh = Platezh.objects.create(
        brigada=brigada,
        summa=summa,
        tarif=tarif,
        status=Platezh.STATUS_OZHIDAET,
        yookassa_id=result['yookassa_id'],
        demo_rezhim=result['demo'],
    )

    if result['demo']:
        _activate_tarif(platezh)
        messages.success(
            request,
            f'Тариф «{conf["label"]}» активирован (демо-режим — ключи ЮKassa не настроены, '
            f'реальных денег не списано).',
        )
        return redirect('billing:plans')

    return redirect(result['confirmation_url'])


def _activate_tarif(platezh: Platezh):
    """Помечает платёж оплаченным и продлевает тариф бригады на 30 дней."""
    platezh.status = Platezh.STATUS_OPLACHEN
    platezh.save(update_fields=['status'])

    brigada = platezh.brigada
    now = timezone.localdate()
    base = brigada.data_okonchaniya_tarifa if (brigada.data_okonchaniya_tarifa and brigada.data_okonchaniya_tarifa > now) else now
    brigada.tarif = platezh.tarif
    brigada.data_okonchaniya_tarifa = base + timedelta(days=30)
    brigada.save(update_fields=['tarif', 'data_okonchaniya_tarifa'])


@login_required
def success(request):
    """Страница возврата после оплаты в ЮKassa (реальный режим — статус подтвердит webhook)."""
    messages.info(request, 'Спасибо! Как только платёж будет подтверждён ЮKassa, тариф обновится автоматически.')
    return redirect('billing:plans')


@csrf_exempt
def webhook(request):
    """
    Приём уведомлений от ЮKassa (раздел 6.1 ТЗ): после успешной оплаты открывает
    доступ и обновляет тариф.

    Телу уведомления не доверяем — ЮKassa его не подписывает. Порядок проверки:
    1) вебхук возможен только с настроенными ключами (в демо-режиме их не бывает);
    2) отправитель — из официальных сетей ЮKassa;
    3) главное: платёж подтверждается встречным запросом к API (статус + сумма).
    Без п.3 любой, кто знает id своего платежа, активировал бы тариф бесплатно.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Только POST')

    if not yookassa_client.is_configured():
        # Ключей нет → настоящих уведомлений быть не может, значит это подделка.
        return HttpResponseForbidden('Приём уведомлений отключён (демо-режим)')

    ip = yookassa_client.klientskiy_ip(request)
    if not yookassa_client.ip_iz_seti_yookassa(ip):
        logger.warning('Вебхук ЮKassa с недоверенного IP: %s', ip)
        return HttpResponseForbidden('IP не из сети ЮKassa')

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest('Некорректный JSON')

    if payload.get('event') != 'payment.succeeded':
        return HttpResponse('OK')  # прочие события игнорируем, но retry не провоцируем

    yookassa_id = (payload.get('object') or {}).get('id')
    if not yookassa_id:
        return HttpResponseBadRequest('Нет id платежа')

    try:
        platezh = Platezh.objects.get(yookassa_id=yookassa_id)
    except Platezh.DoesNotExist:
        return HttpResponseBadRequest('Платёж не найден')

    if not yookassa_client.platezh_deystvitelno_oplachen(platezh):
        logger.warning('Вебхук ЮKassa не подтверждён API для платежа %s', yookassa_id)
        return HttpResponseForbidden('Платёж не подтверждён ЮKassa')

    if platezh.status != Platezh.STATUS_OPLACHEN:
        _activate_tarif(platezh)

    return HttpResponse('OK')


@login_required
def history(request):
    """История платежей бригады."""
    platezhi = Platezh.objects.filter(brigada=request.user.brigada)
    return render(request, 'billing/history.html', {'platezhi': platezhi})
