from dataclasses import dataclass

from django.conf import settings

from .models import LimitTracker


@dataclass
class LimitCheck:
    used: int
    limit: int | None  # None = безлимит
    exceeded: bool

    @property
    def unlimited(self):
        return self.limit is None


def check_limit(brigada, resurs: str) -> LimitCheck:
    """
    Проверка лимита тарифа для ресурса ('dokumenty' | 'raschety' | 'smety').
    Раздел 5 ТЗ: при превышении — модальное окно с предложением апгрейда (жёсткая блокировка);
    при истечении оплаченного периода бригада фактически на «Старте» (Brigada.effective_tarif).
    """
    tariff_conf = settings.TARIFF_LIMITS.get(brigada.effective_tarif, {})
    limit = tariff_conf.get(resurs)

    tracker = LimitTracker.get_or_create_current(brigada)
    used = getattr(tracker, f'{resurs}_ispolzovano')

    if limit is None:
        return LimitCheck(used=used, limit=None, exceeded=False)
    return LimitCheck(used=used, limit=limit, exceeded=used >= limit)
