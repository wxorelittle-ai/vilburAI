from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone

from documents.models import Dokument
from documents.pdf import render_pdf
from .images import process_photo
from .models import FotoAkt

MAX_FOTO = 10
SAMOZANYATY_LIMIT_OBEKTOV = 3  # раздел 5 ТЗ: фото-акты на 3 объектах


def foto_dostupno(brigada) -> bool:
    return brigada.effective_tarif in ('samozanyaty', 'brigadir', 'pro')


def _mozhno_dobavit_na_document(brigada, dokument) -> bool:
    """Лимит по тарифу: у «Самозанятого» фото не более чем на 3 документах."""
    if brigada.effective_tarif != 'samozanyaty':
        return True
    if dokument.fotoakty.exists():
        return True  # к этому документу уже добавляли — не считаем новым
    s_foto = Dokument.objects.filter(brigada=brigada, fotoakty__isnull=False).distinct().count()
    return s_foto < SAMOZANYATY_LIMIT_OBEKTOV


def _regenerate_akt_pdf(dokument):
    """Пересобирает PDF акта приёмки, включая страницу «Фотофиксация»."""
    if dokument.tip != Dokument.TIP_AKT_PRIEMKI:
        return
    ctx = {
        'd': dokument, 'brigada': dokument.brigada, 'pozicii': None,
        'checklist': dokument.checklist, 'is_free_tier': dokument.brigada.tarif == 'start',
        'fotoakty': dokument.fotoakty.all(),
    }
    pdf = render_pdf('documents/pdf/akt_priemki.html', ctx)
    if pdf:
        dokument.pdf_file.save(f'{dokument.nomer}.pdf', ContentFile(pdf), save=True)


@login_required
def upload_foto(request, dokument_pk):
    dokument = get_object_or_404(Dokument, pk=dokument_pk, brigada=request.user.brigada)
    if dokument.tip != Dokument.TIP_AKT_PRIEMKI:
        messages.error(request, 'Фото прикладываются только к акту приёмки этапа.')
        return redirect('documents:detail', pk=dokument.pk)
    if not foto_dostupno(request.user.brigada):
        messages.warning(request, 'Фото-акты доступны с тарифа «Самозанятый».')
        return redirect('billing:plans')
    if not _mozhno_dobavit_na_document(request.user.brigada, dokument):
        messages.warning(request, 'На тарифе «Самозанятый» фото-акты доступны для 3 объектов. Перейдите на «Бригадир» для безлимита.')
        return redirect('billing:plans')

    files = request.FILES.getlist('foto')
    if not files:
        messages.error(request, 'Выберите хотя бы одно фото.')
        return redirect('documents:detail', pk=dokument.pk)

    already = dokument.fotoakty.count()
    svobodno = max(MAX_FOTO - already, 0)
    if svobodno == 0:
        messages.warning(request, f'К одному акту можно приложить не более {MAX_FOTO} фото.')
        return redirect('documents:detail', pk=dokument.pk)

    podpis = (request.POST.get('podpis') or '').strip()
    data_str = timezone.localtime().strftime('%d.%m.%Y %H:%M')
    watermark = [dokument.brigada.nazvanie, dokument.adres_obekta, f'Дата: {data_str}']

    dobavleno = 0
    for f in files[:svobodno]:
        try:
            content, lat, lon = process_photo(f, watermark)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f'Не удалось обработать фото {f.name}: {exc}')
            continue
        foto = FotoAkt(dokument=dokument, watermark_text=' · '.join(watermark),
                       podpis_snizu=podpis, geo_lat=lat, geo_lon=lon)
        foto.foto_file.save(f'foto_{already + dobavleno + 1}.jpg', content, save=True)
        dobavleno += 1

    if dobavleno:
        _regenerate_akt_pdf(dokument)
        messages.success(request, f'Добавлено фото: {dobavleno}. PDF-акт обновлён страницей «Фотофиксация».')
    return redirect('documents:detail', pk=dokument.pk)


@login_required
def delete_foto(request, foto_pk):
    foto = get_object_or_404(FotoAkt, pk=foto_pk, dokument__brigada=request.user.brigada)
    dokument = foto.dokument
    foto.delete()
    _regenerate_akt_pdf(dokument)
    messages.success(request, 'Фото удалено, PDF обновлён.')
    return redirect('documents:detail', pk=dokument.pk)


@login_required
def galereya(request):
    """Галерея фотофиксации: акты приёмки с фото (раздел «Модуль G» ТЗ)."""
    dokumenty = (Dokument.objects
                 .filter(brigada=request.user.brigada, fotoakty__isnull=False)
                 .distinct().prefetch_related('fotoakty').order_by('-data_sozdaniya'))
    return render(request, 'fotoakty/galereya.html', {'dokumenty': dokumenty})
