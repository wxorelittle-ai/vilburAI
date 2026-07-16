"""
Лимиты Модуля J по тарифу (раздел 5 ТЗ):
- «Старт»/«Самозанятый» — модуль недоступен (лимит объектов 0);
- «Бригадир» — до 3 объектов, AI-ассистент 10 запросов/мес;
- «PRO» — объекты и AI безлимит.

Трактовку лимитов берём из общего слоя billing.limits — здесь только то, что
специфично для модуля: как считать «использовано».
"""

from billing import limits as base


def objekty_dostupny(brigada) -> bool:
    """Доступен ли Модуль J на текущем тарифе."""
    return base.dostupen(brigada, 'objekty')


def limit_obektov(brigada):
    """Максимум объектов (None = безлимит)."""
    return base.limit_dlya(brigada, 'objekty')


def ispolzovano_obektov(brigada) -> int:
    """Считаем незавершённые объекты — сданные лимит не занимают."""
    from .models import Objekt
    return Objekt.objects.filter(brigada=brigada).exclude(status=Objekt.STATUS_COMPLETED).count()


def mozhno_sozdat_obekt(brigada) -> bool:
    return base.mozhno(brigada, 'objekty', ispolzovano_obektov(brigada))


def limit_ai(brigada):
    return base.limit_dlya(brigada, 'ai_zaprosy')


def ai_ispolzovano_v_mesyace(brigada) -> int:
    from .models import AiZapros
    return base.za_tekushchiy_mesyac(AiZapros.objects.filter(objekt__brigada=brigada))


def mozhno_sprosit_ai(brigada) -> bool:
    return base.mozhno(brigada, 'ai_zaprosy', ai_ispolzovano_v_mesyace(brigada))
