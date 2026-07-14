from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import render, redirect, get_object_or_404

from billing.limits import check_limit

from .forms import RaschetForm
from .models import Raschet


@login_required
def create_raschet(request):
    """Модуль C: форма расчёта себестоимости с мгновенным результатом (раздел 4.3 ТЗ)."""
    brigada = request.user.brigada

    limit = check_limit(brigada, 'raschety')
    if limit.exceeded:
        messages.warning(request, 'Лимит расчётов по вашему тарифу на этот месяц исчерпан.')
        return redirect('billing:plans')

    if request.method == 'POST':
        form = RaschetForm(request.POST)
        if form.is_valid():
            raschet = form.save(commit=False)
            raschet.brigada = brigada
            raschet.save()
            return redirect('calculator:detail', pk=raschet.pk)
    else:
        form = RaschetForm()

    return render(request, 'calculator/create.html', {'form': form, 'limit_info': limit})


@login_required
def raschet_detail(request, pk):
    """Результат расчёта: себестоимость, рекомендуемые цены, сравнение с рынком."""
    raschet = get_object_or_404(Raschet, pk=pk, brigada=request.user.brigada)
    return render(request, 'calculator/detail.html', {'r': raschet})


@login_required
def raschet_list(request):
    """История расчётов (раздел 4.3 ТЗ)."""
    raschety = Raschet.objects.filter(brigada=request.user.brigada)
    return render(request, 'calculator/list.html', {'raschety': raschety})


@login_required
def raschet_download_xlsx(request, pk):
    """Экспорт расчёта в Excel — PRO-фича (раздел Модуль C ТЗ)."""
    raschet = get_object_or_404(Raschet, pk=pk, brigada=request.user.brigada)
    if request.user.brigada.effective_tarif != 'pro':
        messages.warning(request, 'Экспорт в Excel доступен на тарифе PRO.')
        return redirect('billing:plans')

    from io import BytesIO
    from .excel_export import generate_raschet_xlsx

    xlsx_bytes = generate_raschet_xlsx(raschet)
    return FileResponse(
        BytesIO(xlsx_bytes), as_attachment=True,
        filename=f'Расчёт {raschet.data:%d.%m.%Y}.xlsx',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
