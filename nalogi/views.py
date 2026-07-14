from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from documents.models import Dokument
from . import fns
from .excel_export import cheki_v_excel
from .models import ChekFNS, NalogOtchet

DEN_UPLATY = 25  # срок уплаты налога (раздел «Модуль D» ТЗ)


def nalog_dostupen(brigada) -> bool:
    return brigada.effective_tarif != 'start'


def _limit_cheki(brigada):
    return settings.TARIFF_LIMITS.get(brigada.effective_tarif, {}).get('cheki', 0)


def _cheki_v_mesyace(brigada) -> int:
    now = timezone.localtime()
    return ChekFNS.objects.filter(brigada=brigada, data__year=now.year, data__month=now.month).count()


def _mozhno_probit(brigada) -> bool:
    limit = _limit_cheki(brigada)
    if limit is None:
        return True
    return _cheki_v_mesyace(brigada) < limit


def _napominanie():
    today = timezone.localdate()
    d = today.day
    if d in (22, 23, 24):
        return 'skoro', f'До срока уплаты налога (25-е число) осталось {DEN_UPLATY - d} дн.'
    if d == DEN_UPLATY:
        return 'segodnya', 'Сегодня — срок уплаты налога за прошлый период.'
    return None, None


def _guard(request):
    if not nalog_dostupen(request.user.brigada):
        messages.warning(request, 'Налоговый модуль доступен с тарифа «Самозанятый».')
        return redirect('billing:plans')
    return None


@login_required
def glavnaya(request):
    guard = _guard(request)
    if guard:
        return guard
    brigada = request.user.brigada
    svodka = NalogOtchet.svodka_tekushchaya(brigada)
    tip, tekst = _napominanie()
    limit = _limit_cheki(brigada)
    return render(request, 'nalogi/glavnaya.html', {
        'cheki': ChekFNS.objects.filter(brigada=brigada)[:50],
        'svodka': svodka,
        'napominanie_tip': tip, 'napominanie_tekst': tekst,
        'limit': limit, 'ispolzovano': _cheki_v_mesyace(brigada),
        'demo': not fns.is_configured(),
        'mozhno_probit': _mozhno_probit(brigada),
    })


@login_required
def probit(request):
    guard = _guard(request)
    if guard:
        return guard
    brigada = request.user.brigada

    dokument = None
    dok_id = request.GET.get('dokument') or request.POST.get('dokument_id')
    if dok_id:
        dokument = Dokument.objects.filter(pk=dok_id, brigada=brigada).first()

    if request.method == 'POST':
        if not _mozhno_probit(brigada):
            messages.warning(request, 'Лимит чеков по тарифу на этот месяц исчерпан. Докупите пакет или перейдите на «Бригадир».')
            return redirect('billing:plans')
        try:
            summa = Decimal((request.POST.get('summa') or '0').replace(',', '.'))
        except InvalidOperation:
            summa = Decimal('0')
        if summa <= 0:
            messages.error(request, 'Укажите корректную сумму чека.')
        else:
            chek = ChekFNS.objects.create(
                brigada=brigada, dokument=dokument, summa=summa,
                naznachenie=(request.POST.get('naznachenie') or 'Оплата за работы').strip(),
                telefon_zakazchika=(request.POST.get('telefon') or '').strip(),
                email_zakazchika=(request.POST.get('email') or '').strip(),
            )
            ok, demo = fns.probit_chek(chek)
            if ok:
                messages.success(request, 'Чек пробит и отправлен заказчику.' + (' (демо-режим)' if demo else ''))
            else:
                messages.error(request, 'ФНС вернула ошибку. Проверьте данные и попробуйте позже.')
            return redirect('nalogi:glavnaya')

    prefill = {}
    if dokument:
        prefill = {
            'summa': dokument.avans_summa or dokument.summa,
            'naznachenie': f'Оплата по документу №{dokument.nomer}',
            'telefon': dokument.zakazchik_telefon,
        }
    return render(request, 'nalogi/probit.html', {
        'dokument': dokument, 'prefill': prefill,
        'ispolzovano': _cheki_v_mesyace(brigada), 'limit': _limit_cheki(brigada),
        'demo': not fns.is_configured(),
    })


@login_required
def otchet_oplatit(request):
    """Пометить налог текущего месяца оплаченным."""
    if request.method != 'POST':
        return redirect('nalogi:glavnaya')
    brigada = request.user.brigada
    now = timezone.localtime()
    dohod = NalogOtchet.dohod_za_mesyats(brigada, now.year, now.month)
    otchet, _ = NalogOtchet.objects.get_or_create(brigada=brigada, god=now.year, mesyats=now.month)
    otchet.dohod = dohod
    otchet.nalog_4 = (dohod * Decimal('0.04')).quantize(Decimal('0.01'))
    otchet.nalog_6 = (dohod * Decimal('0.06')).quantize(Decimal('0.01'))
    otchet.status = NalogOtchet.STATUS_OPLACHEN
    otchet.save()
    messages.success(request, 'Налог за текущий месяц отмечен как оплаченный.')
    return redirect('nalogi:glavnaya')


@login_required
def cheki_excel(request):
    guard = _guard(request)
    if guard:
        return guard
    brigada = request.user.brigada
    data = cheki_v_excel(brigada, ChekFNS.objects.filter(brigada=brigada))
    return FileResponse(
        BytesIO(data), as_attachment=True, filename='cheki_fns.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
