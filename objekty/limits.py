"""
Лимиты Модуля J по тарифу (раздел 5 ТЗ):
- «Старт»/«Самозанятый» — модуль недоступен (лимит объектов 0);
- «Бригадир» — до 3 объектов, AI-ассистент 10 запросов/мес;
- «PRO» — объекты и AI безлимит.
"""

from django.conf import settings
from django.utils import timezone


def _conf(brigada):
    return settings.TARIFF_LIMITS.get(brigada.effective_tarif, {})


def objekty_dostupny(brigada) -> bool:
    """Доступен ли Модуль J на текущем тарифе (лимит объектов не ноль)."""
    limit = _conf(brigada).get('objekty', 0)
    return limit is None or limit > 0


def limit_obektov(brigada):
    """Максимум объектов (None = безлимит)."""
    return _conf(brigada).get('objekty', 0)


def mozhno_sozdat_obekt(brigada) -> bool:
    from .models import Objekt
    limit = limit_obektov(brigada)
    if limit is None:
        return True
    if limit == 0:
        return False
    aktivnyh = Objekt.objects.filter(brigada=brigada).exclude(status=Objekt.STATUS_COMPLETED).count()
    return aktivnyh < limit


def limit_ai(brigada):
    return _conf(brigada).get('ai_zaprosy', 0)


def ai_ispolzovano_v_mesyace(brigada) -> int:
    from .models import AiZapros
    now = timezone.localtime()
    return AiZapros.objects.filter(
        objekt__brigada=brigada, data__year=now.year, data__month=now.month,
    ).count()


def mozhno_sprosit_ai(brigada) -> bool:
    limit = limit_ai(brigada)
    if limit is None:
        return True
    if limit == 0:
        return False
    return ai_ispolzovano_v_mesyace(brigada) < limit
