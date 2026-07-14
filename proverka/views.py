from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from . import service
from .models import ProverkaZakazchika


def proverka_dostupna(brigada) -> bool:
    return brigada.effective_tarif in ('brigadir', 'pro')


def _limit(brigada):
    return settings.TARIFF_LIMITS.get(brigada.effective_tarif, {}).get('proverki', 0)


def _v_mesyace(brigada) -> int:
    now = timezone.localtime()
    return ProverkaZakazchika.objects.filter(brigada=brigada, data__year=now.year, data__month=now.month).count()


def _mozhno(brigada) -> bool:
    limit = _limit(brigada)
    return limit is None or _v_mesyace(brigada) < limit


def _guard(request):
    if not proverka_dostupna(request.user.brigada):
        messages.warning(request, 'Проверка заказчика доступна на тарифах «Бригадир» и «PRO».')
        return redirect('billing:plans')
    return None


@login_required
def glavnaya(request):
    guard = _guard(request)
    if guard:
        return guard
    brigada = request.user.brigada
    if request.method == 'POST':
        if not _mozhno(brigada):
            messages.warning(request, 'Лимит проверок по тарифу на этот месяц исчерпан.')
            return redirect('billing:plans')
        tip = request.POST.get('tip_poiska')
        znachenie = (request.POST.get('znachenie') or '').strip()
        if tip not in dict(ProverkaZakazchika.TIP_CHOICES) or not znachenie:
            messages.error(request, 'Укажите ИНН или телефон для проверки.')
        else:
            risk, prichina, detali, demo = service.proverit(tip, znachenie)
            p = ProverkaZakazchika.objects.create(
                brigada=brigada, tip_poiska=tip, znachenie=znachenie,
                status_riska=risk, prichina=prichina, detali=detali, demo_rezhim=demo,
            )
            return redirect('proverka:detail', pk=p.pk)

    return render(request, 'proverka/glavnaya.html', {
        'proverki': ProverkaZakazchika.objects.filter(brigada=brigada)[:50],
        'limit': _limit(brigada), 'ispolzovano': _v_mesyace(brigada),
        'demo': not service.is_configured(),
    })


@login_required
def detail(request, pk):
    guard = _guard(request)
    if guard:
        return guard
    p = get_object_or_404(ProverkaZakazchika, pk=pk, brigada=request.user.brigada)
    return render(request, 'proverka/detail.html', {'p': p})
