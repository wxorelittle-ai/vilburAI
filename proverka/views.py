from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from billing import limits as tarif_limits
from . import service
from .models import ProverkaZakazchika


def proverka_dostupna(brigada) -> bool:
    """Проверка заказчика — с «Бригадира» и выше (ниже лимит 0)."""
    return tarif_limits.dostupen(brigada, 'proverki')


def _limit(brigada):
    return tarif_limits.limit_dlya(brigada, 'proverki')


def _v_mesyace(brigada) -> int:
    return tarif_limits.za_tekushchiy_mesyac(ProverkaZakazchika.objects.filter(brigada=brigada))


def _mozhno(brigada) -> bool:
    return tarif_limits.mozhno(brigada, 'proverki', _v_mesyace(brigada))


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
