"""
Разбор распознанной речи в позиции сметы (Модуль H ТЗ): извлечение работы, объёма и
единицы измерения + fuzzy-подбор из базы цен (BazaCen). Работает без внешних сервисов.

Пример: «укладка плитки 40 квадратов, штукатурка стен 120 метров» →
[{плитка, 40, м²}, {штукатурка стен, 120, м²}].
"""

import re
from difflib import SequenceMatcher

from smety.models import BazaCen

_RAZDELITELI = re.compile(r'\s*(?:[,;]|(?:\bи\b)|(?:\bпотом\b)|(?:\bдалее\b))\s*', re.IGNORECASE)
_CHISLO = re.compile(r'(\d+(?:[.,]\d+)?)')

# Единицы через границы слова: «штук» не должен ловиться внутри «штукатурка».
_EDINICY = [
    (re.compile(r'квадрат\w*|\bкв\.?\s?м\b|\bм2\b|м²', re.IGNORECASE), 'м²'),
    (re.compile(r'погон\w*|\bп\.?\s?м\b', re.IGNORECASE), 'м.п.'),
    (re.compile(r'\bшт\b|\bштук\b|\bштуки\b|\bштука\b|\bштук\.', re.IGNORECASE), 'шт'),
    (re.compile(r'\bметр\w*|\bм\b', re.IGNORECASE), 'м'),
]


def _edinica(chunk):
    for pat, ed in _EDINICY:
        if pat.search(chunk):
            return ed
    return None


def _ochistit_nazvanie(chunk):
    s = _CHISLO.sub(' ', chunk)
    for pat, _ in _EDINICY:
        s = pat.sub(' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' .,-')
    return s


def _luchshee_sovpadenie(nazvanie_low, baza):
    best, best_score = None, 0.0
    for b in baza:
        score = SequenceMatcher(None, nazvanie_low, b.nazvanie.lower()).ratio()
        # бонус за вхождение ключевого слова
        if nazvanie_low and nazvanie_low.split()[0] in b.nazvanie.lower():
            score += 0.15
        if score > best_score:
            best, best_score = b, score
    return best if best_score >= 0.5 else None


def parse_pozicii(text: str, uroven: str = 'srednyaya'):
    baza = list(BazaCen.objects.all())
    result = []
    for chunk in _RAZDELITELI.split(text or ''):
        chunk = chunk.strip()
        if len(chunk) < 3:
            continue
        low = chunk.lower()
        m = _CHISLO.search(chunk)
        kolvo = float(m.group(1).replace(',', '.')) if m else 0
        nazvanie = _ochistit_nazvanie(chunk)
        if not nazvanie:
            continue
        b = _luchshee_sovpadenie(nazvanie.lower(), baza)
        edinica = _edinica(low) or (b.edinica if b else 'м²')
        cena = float(b.cena_dlya_urovnya(uroven)) if b else 0
        result.append({
            'baza_id': b.pk if b else None,
            'nazvanie': b.nazvanie if b else nazvanie.capitalize(),
            'edinica': edinica,
            'kolvo': round(kolvo, 2),
            'cena': cena,
        })
    return result
