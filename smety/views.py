from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404

from billing.limits import check_limit

from .forms import SmetaForm, SmetaRabotaForm, SmetaRabotaFormSet
from .models import Smeta, SmetaRabota, BazaCen
from .pdf import render_smeta_pdf


@login_required
def smeta_list(request):
    """История смет (раздел 4.4 / 7.2 ТЗ)."""
    smety = Smeta.objects.filter(brigada=request.user.brigada).prefetch_related('raboty')
    return render(request, 'smety/list.html', {'smety': smety})


@login_required
def smeta_create(request):
    """Модуль B: конструктор сметы — шапка + позиции (formset с HTMX-добавлением строк)."""
    brigada = request.user.brigada

    limit = check_limit(brigada, 'smety')
    if limit.exceeded:
        messages.warning(request, 'Лимит смет по вашему тарифу на этот месяц исчерпан.')
        return redirect('billing:plans')

    if request.method == 'POST':
        form = SmetaForm(request.POST)
        formset = SmetaRabotaFormSet(request.POST, instance=Smeta())

        if form.is_valid() and formset.is_valid():
            smeta = form.save(commit=False)
            smeta.brigada = brigada
            smeta.save()
            _save_raboty(formset, smeta)
            _generate_and_attach_pdf(smeta)
            messages.success(request, 'Смета создана.')
            return redirect('smety:detail', pk=smeta.pk)
    else:
        form = SmetaForm()
        formset = SmetaRabotaFormSet(instance=Smeta())

    return render(request, 'smety/create.html', {
        'form': form, 'formset': formset, 'limit_info': limit,
        'baza_cen': BazaCen.objects.all(), 'is_edit': False,
    })


@login_required
def smeta_edit(request, pk):
    """Редактирование существующей сметы — только для черновиков."""
    smeta = get_object_or_404(Smeta, pk=pk, brigada=request.user.brigada)

    if request.method == 'POST':
        form = SmetaForm(request.POST, instance=smeta)
        formset = SmetaRabotaFormSet(request.POST, instance=smeta)

        if form.is_valid() and formset.is_valid():
            form.save()
            smeta.raboty.all().delete()
            _save_raboty(formset, smeta)
            _generate_and_attach_pdf(smeta)
            messages.success(request, 'Смета обновлена.')
            return redirect('smety:detail', pk=smeta.pk)
    else:
        form = SmetaForm(instance=smeta)
        formset = SmetaRabotaFormSet(instance=smeta)

    return render(request, 'smety/create.html', {
        'form': form, 'formset': formset, 'limit_info': None,
        'baza_cen': BazaCen.objects.all(), 'is_edit': True, 'smeta': smeta,
    })


def _save_raboty(formset, smeta):
    for i, pform in enumerate(formset):
        if pform.cleaned_data.get('DELETE'):
            continue
        nazvanie = pform.cleaned_data.get('nazvanie')
        if not nazvanie:
            continue
        rabota = pform.save(commit=False)
        rabota.smeta = smeta
        rabota.edinica = pform.cleaned_data.get('edinica') or 'м²'
        rabota.kolvo = pform.cleaned_data.get('kolvo') or 0
        rabota.cena = pform.cleaned_data.get('cena') or 0
        rabota.poryadok = i
        rabota.pk = None  # формсет мог быть привязан к старой строке — всегда создаём заново
        rabota.save()


def _generate_and_attach_pdf(smeta: Smeta):
    context = {
        's': smeta,
        'brigada': smeta.brigada,
        'raboty': smeta.raboty.all(),
        'is_free_tier': smeta.brigada.effective_tarif == 'start',
    }
    pdf_bytes = render_smeta_pdf(context)
    if pdf_bytes:
        smeta.pdf_file.save(f'{smeta.nomer}.pdf', ContentFile(pdf_bytes), save=True)


@login_required
def add_row(request):
    """
    HTMX-эндпоинт: возвращает HTML фрагмент новой пустой строки формсета
    (динамическое добавление без перезагрузки страницы — раздел 7.3 ТЗ).
    """
    index = int(request.GET.get('index', 0))
    form = SmetaRabotaForm(prefix=f'raboty-{index}')
    return render(request, 'smety/_row.html', {'form': form})


@login_required
def add_row_from_baza(request):
    """HTMX-эндпоинт: строка, предзаполненная из базы типовых работ (раздел 4.4 ТЗ)."""
    index = int(request.GET.get('index', 0))
    baza_id = request.GET.get('baza_id')
    uroven = request.GET.get('uroven', 'srednyaya')

    baza = get_object_or_404(BazaCen, pk=baza_id)
    initial = {
        'nazvanie': baza.nazvanie,
        'edinica': baza.edinica,
        'kolvo': 1,
        'cena': baza.cena_dlya_urovnya(uroven),
    }
    form = SmetaRabotaForm(prefix=f'raboty-{index}', initial=initial)
    return render(request, 'smety/_row.html', {'form': form})


@login_required
def smeta_detail(request, pk):
    smeta = get_object_or_404(Smeta, pk=pk, brigada=request.user.brigada)
    return render(request, 'smety/detail.html', {'s': smeta})


@login_required
def smeta_download(request, pk):
    smeta = get_object_or_404(Smeta, pk=pk, brigada=request.user.brigada)
    if not smeta.pdf_file:
        raise Http404('PDF ещё не сформирован')
    return FileResponse(smeta.pdf_file.open('rb'), as_attachment=True, filename=f'Смета {smeta.nomer}.pdf')


@login_required
def smeta_duplicate(request, pk):
    """Дублирование сметы как шаблона для нового объекта (раздел Модуль B ТЗ)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    original = get_object_or_404(Smeta, pk=pk, brigada=request.user.brigada)

    limit = check_limit(request.user.brigada, 'smety')
    if limit.exceeded:
        messages.warning(request, 'Лимит смет по вашему тарифу на этот месяц исчерпан.')
        return redirect('billing:plans')

    kopiya = Smeta.objects.create(
        brigada=original.brigada,
        nazvanie=f'{original.nazvanie} (копия)',
        adres=original.adres,
        zakazchik=original.zakazchik,
        urovne_cen=original.urovne_cen,
        srok_dney=original.srok_dney,
        status='draft',
    )
    for i, rabota in enumerate(original.raboty.all()):
        SmetaRabota.objects.create(
            smeta=kopiya, baza_cen=rabota.baza_cen, nazvanie=rabota.nazvanie,
            edinica=rabota.edinica, kolvo=rabota.kolvo, cena=rabota.cena, poryadok=i,
        )
    _generate_and_attach_pdf(kopiya)
    messages.success(request, 'Смета продублирована.')
    return redirect('smety:detail', pk=kopiya.pk)


@login_required
def smeta_publish(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    smeta = get_object_or_404(Smeta, pk=pk, brigada=request.user.brigada)
    smeta.status = 'public'
    smeta.ensure_public_slug()
    smeta.save(update_fields=['status'])
    messages.success(request, 'Смета опубликована. Ссылку можно отправить заказчику.')
    return redirect('smety:detail', pk=smeta.pk)


@login_required
def smeta_unpublish(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    smeta = get_object_or_404(Smeta, pk=pk, brigada=request.user.brigada)
    smeta.status = 'draft'
    smeta.save(update_fields=['status'])
    messages.info(request, 'Смета снята с публикации.')
    return redirect('smety:detail', pk=smeta.pk)


def public_smeta(request, slug):
    """
    Публичная readonly-страница для заказчика (раздел Модуль B / раздел 8 ТЗ):
    доступна без авторизации, только просмотр (без скачивания), чувствительные
    данные бригады (телефон, реквизиты) скрыты — показывается только название.
    """
    smeta = get_object_or_404(Smeta, public_slug=slug, status='public')
    return render(request, 'smety/public.html', {'s': smeta, 'raboty': smeta.raboty.all()})
