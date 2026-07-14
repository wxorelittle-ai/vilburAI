"""Репутация бригады: рейтинг по отзывам и «подтверждённый» статус (раздел 3 ТЗ)."""

from django.db.models import Avg, Count


def reyting(brigada):
    agg = brigada.otzyvy.filter(opublikovan=True).aggregate(avg=Avg('ocenka'), n=Count('id'))
    return {
        'srednyaya': round(agg['avg'], 1) if agg['avg'] else None,
        'kolvo': agg['n'] or 0,
    }


def podtverzhdena(brigada) -> bool:
    """Подтверждённая бригада: есть подписанный документ (ПЭП), сданный объект или 3+ документа."""
    from documents.models import Dokument
    from podpis.models import PodpisZakazchika
    from objekty.models import Objekt

    if PodpisZakazchika.objects.filter(dokument__brigada=brigada, status=PodpisZakazchika.STATUS_PODPISANO).exists():
        return True
    if Objekt.objects.filter(brigada=brigada, status=Objekt.STATUS_COMPLETED).exists():
        return True
    return Dokument.objects.filter(brigada=brigada).count() >= 3
