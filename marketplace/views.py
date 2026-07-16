from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from core.models import Brigada
from .forms import OtzyvForm, IzlishekForm, TenderForm, OtklikForm
from .models import Otzyv, IzlishekMateriala, Tender, TenderOtklik
from . import reputation

# ------------------------------------------------------------------ Каталог / репутация


def katalog(request):
    """Публичный каталог бригад с рейтингом (раздел 3 / GTM Фаза 3 ТЗ)."""
    q = (request.GET.get('q') or '').strip()
    region = (request.GET.get('region') or '').strip()
    tolko_podtv = request.GET.get('verified') == '1'

    brigady = Brigada.objects.all()
    if q:
        brigady = brigady.filter(nazvanie__icontains=q)
    if region:
        brigady = brigady.filter(region__icontains=region)

    # Всё считаем пакетно: раньше на каждую бригаду уходило 5–6 запросов
    # (рейтинг, «подтверждена», наличие документов/отзывов) — при росте каталога
    # это N+1. Теперь несколько запросов на весь список.
    brigady = list(brigady)
    ids = [b.pk for b in brigady]
    reytingi = reputation.reytingi(ids)
    dok_counts = reputation.kolvo_dokumentov(ids)
    podtv_ids = reputation.podtverzhdennye(ids, dok_counts=dok_counts)

    kartochki = []
    for b in brigady:
        r = reytingi.get(b.pk, {'srednyaya': None, 'kolvo': 0})
        # показываем только «живые» профили: есть документы или отзывы
        if not (r['kolvo'] or dok_counts.get(b.pk)):
            continue
        podtv = b.pk in podtv_ids
        if tolko_podtv and not podtv:
            continue
        kartochki.append({'brigada': b, 'reyting': r, 'podtverzhdena': podtv})
    kartochki.sort(key=lambda k: (k['reyting']['srednyaya'] or 0, k['reyting']['kolvo']), reverse=True)

    regiony = sorted(set(Brigada.objects.exclude(region='').values_list('region', flat=True)))
    return render(request, 'marketplace/katalog.html', {
        'kartochki': kartochki, 'q': q, 'region': region, 'tolko_podtv': tolko_podtv, 'regiony': regiony,
    })


def master(request, pk):
    """Публичный профиль бригады (без телефона/реквизитов — раздел 8 ТЗ)."""
    brigada = get_object_or_404(Brigada, pk=pk)

    if request.method == 'POST':
        form = OtzyvForm(request.POST)
        if form.is_valid():
            otzyv = form.save(commit=False)
            otzyv.brigada = brigada
            otzyv.save()
            messages.success(request, 'Спасибо за отзыв!')
            return redirect('marketplace:master', pk=brigada.pk)
    else:
        form = OtzyvForm()

    return render(request, 'marketplace/master.html', {
        'brigada': brigada, 'reyting': reputation.reyting(brigada),
        'podtverzhdena': reputation.podtverzhdena(brigada),
        'otzyvy': brigada.otzyvy.filter(opublikovan=True),
        'izlishki': brigada.izlishki.filter(status=IzlishekMateriala.STATUS_AKTIVNO),
        'form': form,
    })


# ------------------------------------------------------------------ Биржа излишков


def birzha(request):
    q = (request.GET.get('q') or '').strip()
    region = (request.GET.get('region') or '').strip()
    izlishki = IzlishekMateriala.objects.filter(status=IzlishekMateriala.STATUS_AKTIVNO).select_related('brigada')
    if q:
        izlishki = izlishki.filter(nazvanie__icontains=q)
    if region:
        izlishki = izlishki.filter(region__icontains=region)
    return render(request, 'marketplace/birzha.html', {'izlishki': izlishki, 'q': q, 'region': region})


@login_required
def izlishek_create(request):
    if request.method == 'POST':
        form = IzlishekForm(request.POST)
        if form.is_valid():
            izl = form.save(commit=False)
            izl.brigada = request.user.brigada
            if not izl.region:
                izl.region = request.user.brigada.region
            izl.save()
            messages.success(request, 'Объявление размещено на бирже.')
            return redirect('marketplace:birzha')
    else:
        form = IzlishekForm(initial={'kontakt_telefon': request.user.brigada.telefon, 'region': request.user.brigada.region})
    return render(request, 'marketplace/izlishek_form.html', {'form': form})


@login_required
def izlishek_snyat(request, pk):
    izl = get_object_or_404(IzlishekMateriala, pk=pk, brigada=request.user.brigada)
    izl.status = IzlishekMateriala.STATUS_PRODANO
    izl.save(update_fields=['status'])
    messages.success(request, 'Объявление снято.')
    return redirect('marketplace:birzha')


# ------------------------------------------------------------------ Тендеры


def tendery(request):
    spisok = Tender.objects.select_related('brigada').all()
    return render(request, 'marketplace/tendery.html', {'tendery': spisok})


@login_required
def tender_create(request):
    if request.method == 'POST':
        form = TenderForm(request.POST)
        if form.is_valid():
            t = form.save(commit=False)
            t.brigada = request.user.brigada
            t.save()
            messages.success(request, 'Заявка опубликована. Бригады пришлют предложения.')
            return redirect('marketplace:tender_detail', pk=t.pk)
    else:
        form = TenderForm(initial={'region': request.user.brigada.region})
    return render(request, 'marketplace/tender_form.html', {'form': form})


def tender_detail(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    moya = request.user.is_authenticated and tender.brigada == getattr(request.user, 'brigada', None)
    moy_otklik = None
    if request.user.is_authenticated:
        moy_otklik = tender.otkliki.filter(brigada=request.user.brigada).first()

    if request.method == 'POST' and request.user.is_authenticated and not moya:
        if not tender.otkryt:
            messages.warning(request, 'Тендер закрыт — отклики не принимаются.')
            return redirect('marketplace:tender_detail', pk=pk)
        form = OtklikForm(request.POST, instance=moy_otklik)
        if form.is_valid():
            otk = form.save(commit=False)
            otk.tender = tender
            otk.brigada = request.user.brigada
            otk.save()
            messages.success(request, 'Ваше предложение отправлено.')
            return redirect('marketplace:tender_detail', pk=pk)
    else:
        form = OtklikForm(instance=moy_otklik)

    # Автор видит все отклики; остальные — только свой и общее число
    otkliki = tender.otkliki.select_related('brigada').all() if moya else None
    return render(request, 'marketplace/tender_detail.html', {
        'tender': tender, 'moya': moya, 'otkliki': otkliki,
        'moy_otklik': moy_otklik, 'form': form,
    })


@login_required
def tender_zakryt(request, pk):
    tender = get_object_or_404(Tender, pk=pk, brigada=request.user.brigada)
    tender.status = Tender.STATUS_ZAKRYT
    tender.save(update_fields=['status'])
    messages.success(request, 'Тендер закрыт.')
    return redirect('marketplace:tender_detail', pk=pk)
