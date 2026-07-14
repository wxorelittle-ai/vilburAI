"""
Риск-скоринг заказчика (раздел 6.5 ТЗ).

Без ключа (KONTUR_API_KEY) — демо-режим: проверка по внутреннему чёрному списку +
детерминированная псевдо-оценка по значению (стабильна для одного и того же ИНН/телефона).
С ключом включается реальный запрос к Контур/СПАРК (заглушка для боевого подключения).
"""

import hashlib

from django.conf import settings

from .models import ProverkaZakazchika, ChyornySpisok

RUKOVODITELI = ['Иванов И.И.', 'Петров П.П.', 'Сидорова А.В.', 'Кузнецов Д.М.', 'Морозова Е.С.']
GORODA = ['г. Тюмень', 'г. Тюмень, ул. Республики', 'г. Тюмень, ул. Мельникайте', 'г. Ялуторовск']


def is_configured() -> bool:
    return bool(getattr(settings, 'KONTUR_API_KEY', ''))


def _hash_int(value: str) -> int:
    return int(hashlib.sha256(value.encode('utf-8')).hexdigest(), 16)


def proverit(tip: str, znachenie: str):
    """Возвращает (status_riska, prichina, detali: dict, demo: bool)."""
    znachenie = znachenie.strip()

    # 1. Внутренний чёрный список — приоритетный сигнал
    if tip == ProverkaZakazchika.TIP_TELEFON:
        cs = ChyornySpisok.objects.filter(telefon=znachenie).first()
    else:
        cs = ChyornySpisok.objects.filter(inn=znachenie).first()
    if cs:
        return (ProverkaZakazchika.RISK_VYSOKY,
                f'В чёрном списке: {cs.prichina} (жалоб: {cs.kolvo_zhalob})',
                {'chyorny_spisok': True, 'istochnik': cs.get_istochnik_display(), 'zhalob': cs.kolvo_zhalob},
                not is_configured())

    if is_configured():
        # Боевой режим: здесь запрос к Контур/СПАРК по settings.KONTUR_API_KEY.
        pass  # заглушка — при подключении реального ключа

    h = _hash_int(znachenie)
    if tip == ProverkaZakazchika.TIP_INN:
        arbitr = h % 6
        deystvuet = (h // 7) % 10 != 0  # ~10% недействующих
        detali = {
            'status': 'Действующее' if deystvuet else 'Недействующее / в ликвидации',
            'rukovoditel': RUKOVODITELI[h % len(RUKOVODITELI)],
            'adres': GORODA[h % len(GORODA)],
            'arbitrazhnyh_del': arbitr,
        }
        if not deystvuet or arbitr >= 3:
            risk, prichina = ProverkaZakazchika.RISK_VYSOKY, f'Арбитражных дел: {arbitr}' + ('' if deystvuet else ', статус недействующий')
        elif arbitr >= 1:
            risk, prichina = ProverkaZakazchika.RISK_SREDNY, f'Есть арбитражные дела: {arbitr}'
        else:
            risk, prichina = ProverkaZakazchika.RISK_NIZKY, 'Действующее юрлицо, арбитражных дел нет'
    else:
        zhalob = h % 4
        detali = {'incidentov_neoplaty': zhalob}
        if zhalob >= 2:
            risk, prichina = ProverkaZakazchika.RISK_VYSOKY, f'Инцидентов неоплаты в базе: {zhalob}'
        elif zhalob == 1:
            risk, prichina = ProverkaZakazchika.RISK_SREDNY, 'Есть один инцидент неоплаты'
        else:
            risk, prichina = ProverkaZakazchika.RISK_NIZKY, 'Инцидентов неоплаты не найдено'

    return risk, prichina, detali, not is_configured()
