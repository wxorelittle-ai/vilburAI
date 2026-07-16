"""Репутация бригады: рейтинг по отзывам и «подтверждённый» статус (раздел 3 ТЗ).

Есть две версии каждой проверки:
- для одной бригады (карточка мастера) — reyting() / podtverzhdena();
- пакетные для каталога — reytingi() / podtverzhdennye() / kolvo_dokumentov():
  считают всё за несколько запросов на весь список вместо 5–6 запросов на бригаду.
Правило «подтверждённости» описано один раз — в _PODTVERZHDENIE_DOK_MIN и ниже.
"""

from django.db.models import Avg, Count

_PODTVERZHDENIE_DOK_MIN = 3


# --- одна бригада -------------------------------------------------------------

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
    return Dokument.objects.filter(brigada=brigada).count() >= _PODTVERZHDENIE_DOK_MIN


# --- пакетные версии для каталога ----------------------------------------------

def reytingi(brigada_ids) -> dict:
    """{brigada_id: {'srednyaya', 'kolvo'}} одним запросом."""
    from .models import Otzyv
    agg = (Otzyv.objects.filter(brigada_id__in=brigada_ids, opublikovan=True)
           .values('brigada').annotate(avg=Avg('ocenka'), n=Count('id')))
    return {
        r['brigada']: {'srednyaya': round(r['avg'], 1) if r['avg'] else None, 'kolvo': r['n']}
        for r in agg
    }


def kolvo_dokumentov(brigada_ids) -> dict:
    """{brigada_id: сколько документов} одним запросом."""
    from documents.models import Dokument
    return {r['brigada']: r['n'] for r in
            Dokument.objects.filter(brigada_id__in=brigada_ids).values('brigada').annotate(n=Count('id'))}


def podtverzhdennye(brigada_ids, dok_counts=None) -> set:
    """Множество id подтверждённых бригад — то же правило, что в podtverzhdena(),
    но тремя запросами на весь список."""
    from documents.models import Dokument
    from podpis.models import PodpisZakazchika
    from objekty.models import Objekt

    ids = set()
    ids |= set(PodpisZakazchika.objects
               .filter(dokument__brigada_id__in=brigada_ids, status=PodpisZakazchika.STATUS_PODPISANO)
               .values_list('dokument__brigada_id', flat=True))
    ids |= set(Objekt.objects
               .filter(brigada_id__in=brigada_ids, status=Objekt.STATUS_COMPLETED)
               .values_list('brigada_id', flat=True))
    if dok_counts is None:
        dok_counts = kolvo_dokumentov(brigada_ids)
    ids |= {bid for bid, n in dok_counts.items() if n >= _PODTVERZHDENIE_DOK_MIN}
    return ids
