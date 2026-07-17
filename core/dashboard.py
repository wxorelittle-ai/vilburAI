"""
Сборка данных для главного экрана: «что горит», объекты и деньги.

Идея взята из реворка главного экрана (секции-карусели с цветовыми классами),
но наполнена нашими настоящими дедлайнами: у бригады «задачи» — это не планёрки,
а крайние даты заказа материалов, старты/финиши этапов, ожидаемые платежи
от заказчика и срок уплаты налога.
"""

from datetime import date, timedelta

from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone

GORIZONT_DNEY = 14      # окно «ближайших дел»
DEN_UPLATY_NALOGA = 25  # раздел «Модуль D» ТЗ

MESYATSY = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
DNI_NEDELI = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


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


"""Календарь месяца — ниже."""

KATEGORII = [
    ('material', 'Заказ материала', 'amber'),
    ('etap', 'Сдача выполнения', 'steel'),
    ('dengi', 'Получение денег', 'blue'),
    ('zarplata', 'Зарплата рабочим', 'green'),
]


def _mesyats_sosed(god, mesyats, shag):
    """Соседний месяц (shag=-1 предыдущий, +1 следующий)."""
    m = mesyats + shag
    if m < 1:
        return god - 1, 12
    if m > 12:
        return god + 1, 1
    return god, m


def kalendar_mesyaca(brigada, god=None, mesyats=None, objekty=None):
    """
    Сетка календаря на месяц: недели × 7 дней, в каждом дне — задачи бригады.

    Цвет задачи — по её виду (см. KATEGORII), но если задача не выполнена и просрочена
    на день и более — она красная независимо от вида. Задача «на сегодня» ещё не
    просрочена: горит только то, чей срок был вчера или раньше.
    """
    import calendar as cal
    from objekty.models import Material, DvizhenieDeneg

    today = timezone.localdate()
    god = god or today.year
    mesyats = mesyats or today.month
    pervoe = date(god, mesyats, 1)
    posledneye = date(god, mesyats, cal.monthrange(god, mesyats)[1])

    # события копим по датам: {date: [событие, ...]}
    po_dnyam = {}

    def dobavit(data, tip, zagolovok, podzagolovok, url, vypolneno):
        if not (pervoe <= data <= posledneye):
            return
        prosr = (not vypolneno) and data < today      # «на день и более»
        po_dnyam.setdefault(data, []).append({
            'tip': tip,
            'cvet': 'red' if prosr else dict((k, c) for k, _, c in KATEGORII)[tip],
            'zagolovok': zagolovok, 'podzagolovok': podzagolovok,
            'url': url, 'prosrocheno': prosr, 'vypolneno': vypolneno,
        })

    for ob in (objekty if objekty is not None else _objekty_brigady(brigada)):
        url = reverse('objekty:detail', args=[ob.pk])

        for m in ob.materialy.all():
            kraynyaya = m.data_zakaza_kraynyaya
            if kraynyaya:
                dobavit(kraynyaya, 'material', f'Заказать: {m.nazvanie}',
                        f'{ob.nazvanie} · этап «{m.etap.nazvanie}»', url + '?tab=materialy',
                        vypolneno=m.status != Material.STATUS_NE_ZAKAZAN)

        for e in ob.etapy.all():
            dobavit(e.plan_data_okonchania, 'etap', f'Сдать: {e.nazvanie}',
                    f'{ob.nazvanie} · готовность {e.procent}%', url + '?tab=grafik',
                    vypolneno=e.procent >= 100)

        for d in ob.dvizhenie_deneg.all():
            dobavit(d.data_plan, 'dengi', f'Получить: {d.summa_nachislenie:.0f} ₽',
                    f'{ob.nazvanie} · {d.osnovanie}', url + '?tab=dengi',
                    vypolneno=d.status == DvizhenieDeneg.STATUS_POLUCHENO)

        for o in ob.oplaty_montajnikov.all():
            if o.summa_k_oplate <= 0:
                continue
            dobavit(o.data_vyplaty_plan, 'zarplata', f'Зарплата: {o.montajnik_fio}',
                    f'{ob.nazvanie} · {o.ostatok_k_vyplate:.0f} ₽ к выплате', url + '?tab=oplata',
                    vypolneno=o.vyplacheno_polnostyu)

    # раскладываем по неделям (понедельник — первый день)
    nedeli = []
    for nedelya in cal.Calendar(firstweekday=0).monthdatescalendar(god, mesyats):
        dni = []
        for d in nedelya:
            sobytiya = sorted(po_dnyam.get(d, []), key=lambda s: (not s['prosrocheno'], s['tip']))
            dni.append({
                'data': d, 'den': d.day,
                'v_mesyatse': d.month == mesyats,
                'segodnya': d == today,
                'sobytiya': sobytiya,
                'prosrocheno': any(s['prosrocheno'] for s in sobytiya),
            })
        nedeli.append(dni)

    vse = [s for spisok in po_dnyam.values() for s in spisok]
    pg, pm = _mesyats_sosed(god, mesyats, -1)
    sg, sm = _mesyats_sosed(god, mesyats, +1)
    return {
        'god': god, 'mesyats': mesyats,
        'nazvanie': f'{MESYATSY[mesyats - 1]} {god}',
        'nedeli': nedeli,
        'legenda': [{'tip': k, 'nazvanie': n, 'cvet': c} for k, n, c in KATEGORII],
        'vsego': len(vse),
        'prosrocheno': sum(1 for s in vse if s['prosrocheno']),
        'pred': {'god': pg, 'mesyats': pm},
        'sled': {'god': sg, 'mesyats': sm},
        'etot_mesyats': {'god': today.year, 'mesyats': today.month},
        'tekushchiy': (god, mesyats) == (today.year, today.month),
    }


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
