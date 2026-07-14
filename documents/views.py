from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404

from billing.limits import check_limit
from core.models import Brigada

from .forms import DogovorForm, RaspiskaForm, AktPriemkiForm, AktVkrForm, PoziciaFormSet
from .models import Dokument
from .pdf import render_pdf

TIP_FORMS = {
    Dokument.TIP_DOGOVOR: (DogovorForm, 'documents/pdf/dogovor.html'),
    Dokument.TIP_RASPISKA: (RaspiskaForm, 'documents/pdf/raspiska.html'),
    Dokument.TIP_AKT_PRIEMKI: (AktPriemkiForm, 'documents/pdf/akt_priemki.html'),
    Dokument.TIP_AKT_VKR: (AktVkrForm, 'documents/pdf/akt_vkr.html'),
}

TIP_KARTOCHKI = [
    {'kod': Dokument.TIP_DOGOVOR, 'nazvanie': 'Договор подряда',
     'opisanie': 'Оплата 30/40/30, штрафы, гарантия 1 год, порядок расторжения'},
    {'kod': Dokument.TIP_AKT_VKR, 'nazvanie': 'Акт выполненных работ',
     'opisanie': 'Таблица работ с автоподсчётом суммы'},
    {'kod': Dokument.TIP_AKT_PRIEMKI, 'nazvanie': 'Акт приёмки этапа',
     'opisanie': '10 пунктов чек-листа, защита от переделок'},
    {'kod': Dokument.TIP_RASPISKA, 'nazvanie': 'Расписка об авансе',
     'opisanie': 'С условием невозврата при отказе заказчика'},
]


@login_required
def choose_type(request):
    """Модуль A, шаг 1 wizard'а: выбор типа документа (раздел 7.2 ТЗ)."""
    return render(request, 'documents/choose_type.html', {'tipy': TIP_KARTOCHKI})


@login_required
def create_document(request, tip):
    """Модуль A, шаг 2 wizard'а: заполнение формы, генерация PDF, сохранение."""
    if tip not in TIP_FORMS:
        raise Http404

    brigada = request.user.brigada
    FormClass, pdf_template = TIP_FORMS[tip]
    is_vkr = tip == Dokument.TIP_AKT_VKR

    limit = check_limit(brigada, 'dokumenty')
    if limit.exceeded:
        messages.warning(request, 'Лимит документов по вашему тарифу на этот месяц исчерпан.')
        return redirect('billing:plans')

    if request.method == 'POST':
        form = FormClass(request.POST)
        formset = PoziciaFormSet(request.POST, instance=Dokument()) if is_vkr else None

        form_valid = form.is_valid()
        formset_valid = formset.is_valid() if formset else True

        if form_valid and formset_valid:
            dokument = form.save(commit=False)
            dokument.brigada = brigada
            dokument.tip = tip
            if tip == Dokument.TIP_AKT_PRIEMKI:
                dokument.checklist = Dokument.DEFAULT_CHECKLIST
            dokument.save()

            if is_vkr:
                for pform in formset:
                    if pform.cleaned_data.get('DELETE'):
                        continue
                    nazvanie = pform.cleaned_data.get('nazvanie')
                    if not nazvanie:
                        continue  # пустая «лишняя» строка — пропускаем
                    pozicia = pform.save(commit=False)
                    pozicia.dokument = dokument
                    pozicia.edinica = pform.cleaned_data.get('edinica') or 'м²'
                    pozicia.kolvo = pform.cleaned_data.get('kolvo') or 0
                    pozicia.cena = pform.cleaned_data.get('cena') or 0
                    pozicia.save()

            _generate_and_attach_pdf(dokument, pdf_template, brigada)
            messages.success(request, 'Документ создан и готов к скачиванию.')
            return redirect('documents:detail', pk=dokument.pk)
    else:
        form = FormClass()
        formset = PoziciaFormSet(instance=Dokument()) if is_vkr else None

    context = {
        'form': form,
        'formset': formset,
        'tip': tip,
        'tip_label': dict(Dokument.TIP_CHOICES)[tip],
        'limit_info': limit,
    }
    return render(request, 'documents/create.html', context)


def _generate_and_attach_pdf(dokument: Dokument, pdf_template: str, brigada: Brigada):
    context = {
        'd': dokument,
        'brigada': brigada,
        'pozicii': dokument.pozicii.all() if dokument.tip == Dokument.TIP_AKT_VKR else None,
        'checklist': dokument.checklist,
        'is_free_tier': brigada.tarif == 'start',
    }
    pdf_bytes = render_pdf(pdf_template, context)
    if pdf_bytes:
        dokument.pdf_file.save(f'{dokument.nomer}.pdf', ContentFile(pdf_bytes), save=True)


@login_required
def document_list(request):
    """История документов бригады (раздел 4.2 / 7.2 ТЗ)."""
    dokumenty = Dokument.objects.filter(brigada=request.user.brigada)
    return render(request, 'documents/list.html', {'dokumenty': dokumenty})


@login_required
def document_detail(request, pk):
    """Просмотр документа после создания: карточка + ссылка на скачивание PDF."""
    dokument = get_object_or_404(Dokument, pk=pk, brigada=request.user.brigada)
    return render(request, 'documents/detail.html', {'d': dokument})


@login_required
def document_download(request, pk):
    """Скачивание PDF. Доступ — только владелец (раздел 8 ТЗ)."""
    dokument = get_object_or_404(Dokument, pk=pk, brigada=request.user.brigada)
    if not dokument.pdf_file:
        raise Http404('PDF ещё не сформирован')
    return FileResponse(dokument.pdf_file.open('rb'), as_attachment=True,
                         filename=f'{dokument.get_tip_display()} {dokument.nomer}.pdf')


@login_required
def document_download_docx(request, pk):
    """Скачивание Word-версии — PRO-фича (раздел Модуль A ТЗ)."""
    dokument = get_object_or_404(Dokument, pk=pk, brigada=request.user.brigada)
    if request.user.brigada.effective_tarif != 'pro':
        messages.warning(request, 'Экспорт в Word доступен на тарифе PRO.')
        return redirect('billing:plans')

    from io import BytesIO
    from .docx_export import generate_docx

    docx_bytes = generate_docx(dokument)
    return FileResponse(
        BytesIO(docx_bytes), as_attachment=True,
        filename=f'{dokument.get_tip_display()} {dokument.nomer}.docx',
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
