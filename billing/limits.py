"""
Единый слой лимитов по тарифу (раздел 5 ТЗ).

Все модули спрашивают лимиты только отсюда — иначе правила расползаются: раньше
TARIFF_LIMITS читали и трактовали независимо в четырёх местах (billing, objekty,
nalogi, proverka).

Семантика значения в settings.TARIFF_LIMITS:
    None — безлимит;
    0    — ресурс недоступен на этом тарифе;
    N    — не больше N за расчётный период.

«Использовано» каждый модуль считает по-своему (счётчики LimitTracker, записи за
месяц, общее число объектов), поэтому счёт передаётся в proverit() снаружи,
а трактовка лимита — общая.
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from .models import LimitTracker


@dataclass
class LimitCheck:
    used: int
    limit: int | None  # None = безлимит
    exceeded: bool

    @property
    def unlimited(self):
        return self.limit is None


# --- Общие правила -------------------------------------------------------------

def limit_dlya(brigada, resurs):
    """Лимит ресурса по ДЕЙСТВУЮЩЕМУ тарифу (истёкшая подписка → «Старт»).
    Неизвестный ресурс считаем недоступным (0), а не безлимитным."""
    return settings.TARIFF_LIMITS.get(brigada.effective_tarif, {}).get(resurs, 0)


def dostupen(brigada, resurs) -> bool:
    """Доступен ли ресурс/модуль на тарифе вообще (лимит не ноль)."""
    limit = limit_dlya(brigada, resurs)
    return limit is None or limit > 0


def proverit(brigada, resurs, ispolzovano: int) -> LimitCheck:
    """Сравнить использованное с лимитом тарифа."""
    limit = limit_dlya(brigada, resurs)
    if limit is None:
        return LimitCheck(used=ispolzovano, limit=None, exceeded=False)
    return LimitCheck(used=ispolzovano, limit=limit, exceeded=ispolzovano >= limit)


def mozhno(brigada, resurs, ispolzovano: int) -> bool:
    """Можно ли сделать ещё одно действие с этим ресурсом."""
    return not proverit(brigada, resurs, ispolzovano).exceeded


def za_tekushchiy_mesyac(queryset, data_field: str = 'data') -> int:
    """Сколько записей набежало в текущем месяце — общий счётчик для чеков ФНС,
    проверок заказчика и запросов к AI-ассистенту."""
    now = timezone.localtime()
    return queryset.filter(**{f'{data_field}__year': now.year,
                              f'{data_field}__month': now.month}).count()


# --- Ресурсы со счётчиками LimitTracker (документы / расчёты / сметы) ----------

def check_limit(brigada, resurs: str) -> LimitCheck:
    """
    Проверка лимита для ресурса со счётчиком ('dokumenty' | 'raschety' | 'smety').
    Раздел 5 ТЗ: при превышении — предложение апгрейда (жёсткая блокировка);
    при истечении оплаченного периода бригада фактически на «Старте»
    (см. Brigada.effective_tarif).
    """
    tracker = LimitTracker.get_or_create_current(brigada)
    used = getattr(tracker, f'{resurs}_ispolzovano')
    return proverit(brigada, resurs, used)
