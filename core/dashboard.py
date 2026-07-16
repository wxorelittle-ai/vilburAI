"""
Сборка данных для главного экрана: «что горит», объекты и деньги.

Идея взята из реворка главного экрана (секции-карусели с цветовыми классами),
но наполнена нашими настоящими дедлайнами: у бригады «задачи» — это не планёрки,
а крайние даты заказа материалов, старты/финиши этапов, ожидаемые платежи
от заказчика и срок уплаты налога.
"""

from datetime import timedelta

from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone

GORIZONT_DNEY = 14      # окно «ближайших дел»
DEN_UPLATY_NALOGA = 25  # раздел «Модуль D» ТЗ


def _objekty_brigady(brigada):
    from objekty.models import Objekt, Material
    return (Objekt.objects.filter(brigada=brigada)
            .exclude(status=Objekt.STATUS_COMPLETED)
            .prefetch_related(
                'etapy', 'dvizhenie_deneg', 'rashody', 'oplaty_montajnikov',
                Prefetch('materialy', queryset=Material.objects.select_related('etap')),
            ))


def blizhayshie_dela(brigada, dney: int = GORIZONT_DNEY, objekty=None):
    """
    Лента ближайших дел, отсортированная по дате. Каждый элемент:
    {data, ton, tip, zagolovok, podzagolovok, url, prosrocheno}

    ton: 'red' — просрочено/горит, 'amber' — скоро, 'blue' — деньги, 'steel' — прочее.
    """
    from objekty.models import Material, DvizhenieDeneg

    today = timezone.localdate()
    gorizont = today + timedelta(days=dney)
    dela = []

    for ob in (objekty if objekty is not None else _objekty_brigady(brigada)):
        url = reverse('objekty:detail', args=[ob.pk])

        # Материалы: заказать вовремя — иначе встанет этап
        for m in ob.materialy.all():
            if m.status != Material.STATUS_NE_ZAKAZAN:
                continue
            kraynyaya = m.data_zakaza_kraynyaya
            if not kraynyaya or kraynyaya > gorizont:
                continue
            prosr = kraynyaya < today
            dela.append({
                'data': kraynyaya, 'ton': 'red' if prosr else 'amber', 'tip': 'Материал',
                'zagolovok': ('Просрочен заказ: ' if prosr else 'Заказать: ') + m.nazvanie,
                'podzagolovok': f'{ob.nazvanie} · этап «{m.etap.nazvanie}»',
                'url': url + '?tab=materialy', 'prosrocheno': prosr,
            })

        # Этапы: что стартует и что должно закрыться
        for e in ob.etapy.all():
            if today <= e.plan_data_nachala <= gorizont:
                dela.append({
                    'data': e.plan_data_nachala, 'ton': 'steel', 'tip': 'Этап',
                    'zagolovok': 'Старт: ' + e.nazvanie, 'podzagolovok': ob.nazvanie,
                    'url': url + '?tab=grafik', 'prosrocheno': False,
                })
            if today <= e.plan_data_okonchania <= gorizont and e.procent < 100:
                dela.append({
                    'data': e.plan_data_okonchania, 'ton': 'amber', 'tip': 'Этап',
                    'zagolovok': f'Сдать: {e.nazvanie} ({e.procent}%)', 'podzagolovok': ob.nazvanie,
                    'url': url + '?tab=grafik', 'prosrocheno': False,
                })

        # Деньги от заказчика: ожидаемые и просроченные поступления
        for d in ob.dvizhenie_deneg.all():
            if d.status == DvizhenieDeneg.STATUS_POLUCHENO or d.data_plan > gorizont:
                continue
            prosr = d.data_plan < today
            dela.append({
                'data': d.data_plan, 'ton': 'red' if prosr else 'blue', 'tip': 'Деньги',
                'zagolovok': ('Просрочен платёж: ' if prosr else 'Ожидается: ') + f'{d.summa_nachislenie} ₽',
                'podzagolovok': f'{ob.nazvanie} · {d.osnovanie}',
                'url': url + '?tab=dengi', 'prosrocheno': prosr,
            })

    # Налог — общий для бригады, не по объекту
    srok_naloga = today.replace(day=DEN_UPLATY_NALOGA)
    if srok_naloga < today:  # в этом месяце срок прошёл — берём следующий
        srok_naloga = (srok_naloga + timedelta(days=32)).replace(day=DEN_UPLATY_NALOGA)
    if srok_naloga <= gorizont:
        from billing import limits as tarif_limits
        if tarif_limits.dostupen(brigada, 'cheki'):
            dela.append({
                'data': srok_naloga, 'ton': 'amber', 'tip': 'Налог',
                'zagolovok': 'Срок уплаты налога', 'podzagolovok': 'Проверьте сводку доходов',
                'url': reverse('nalogi:glavnaya'), 'prosrocheno': False,
            })

    dela.sort(key=lambda d: (d['data'], 0 if d['ton'] == 'red' else 1))
    return dela


def finansy(brigada, objekty=None):
    """Сводка денег по незавершённым объектам."""
    from decimal import Decimal
    obs = list(objekty if objekty is not None else _objekty_brigady(brigada))
    poluchen = sum((o.prihod_poluchen for o in obs), Decimal('0'))
    ozhidaetsya = sum((o.prihod_ozhidaetsya for o in obs), Decimal('0'))
    rashod = sum((o.rashod_itogo for o in obs), Decimal('0'))
    return {
        'poluchen': poluchen,
        'ozhidaetsya': ozhidaetsya,
        'rashod': rashod,
        'balans': poluchen - rashod,
        'razryvy': [o for o in obs if o.est_kassovy_razryv],
    }
