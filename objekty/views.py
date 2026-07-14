"""Модуль J — контроль объектов. Вьюхи: сводный дашборд, карточка объекта с
вкладками (график / материалы / оплата / расходы / деньги / AI-ассистент)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from smety.models import Smeta
from . import ai_assistant, limits
from .forms import (
    ObjektForm, EtapGrafikaForm, FactObjemForm, MaterialForm,
    OplataMontajnikaForm, RashodMesyachnyForm, DvizhenieDenegForm,
)
from .models import (
    Objekt, EtapGrafika, Material, OplataMontajnika, RashodMesyachny,
    DvizhenieDeneg, AiZapros,
)


def _guard_module(request):
    """Возвращает redirect на тарифы, если Модуль J недоступен на тарифе бригады."""
    if not limits.objekty_dostupny(request.user.brigada):
        messages.warning(request, 'Модуль «Контроль объектов» доступен на тарифах «Бригадир» и «PRO».')
        return redirect('billing:plans')
    return None


@login_required
def obekty_list(request):
    guard = _guard_module(request)
    if guard:
        return guard
    obekty = list(Objekt.objects.filter(brigada=request.user.brigada))
    trebuyut_vnimaniya = [o for o in obekty if o.krasnye_flagi]
    return render(request, 'objekty/list.html', {
        'obekty': obekty,
        'trebuyut_vnimaniya': trebuyut_vnimaniya,
        'limit_obektov': limits.limit_obektov(request.user.brigada),
    })


@login_required
def obekt_create(request):
    guard = _guard_module(request)
    if guard:
        return guard

    brigada = request.user.brigada
    if not limits.mozhno_sozdat_obekt(brigada):
        messages.warning(request, 'Достигнут лимит объектов по вашему тарифу. Перейдите на PRO для безлимита.')
        return redirect('billing:plans')

    # Предзаполнение из сметы (Смета → Объект, раздел 4.8 ТЗ)
    smeta = None
    smeta_id = request.GET.get('smeta') or request.POST.get('smeta_id')
    if smeta_id:
        smeta = Smeta.objects.filter(pk=smeta_id, brigada=brigada).first()

    if request.method == 'POST':
        form = ObjektForm(request.POST)
        if form.is_valid():
            objekt = form.save(commit=False)
            objekt.brigada = brigada
            objekt.smeta = smeta
            objekt.save()
            if smeta:
                _create_etapy_from_smeta(objekt, smeta)
                messages.success(request, f'Объект создан, график собран из сметы «{smeta.nazvanie}».')
            else:
                messages.success(request, 'Объект создан. Добавьте этапы графика вручную.')
            return redirect('objekty:detail', pk=objekt.pk)
    else:
        initial = {}
        if smeta:
            initial = {
                'nazvanie': smeta.nazvanie,
                'adres': smeta.adres,
                'zakazchik': smeta.zakazchik,
                'summa_dogovora': smeta.itogo,
                'data_nachala': timezone.localdate(),
                'data_okonchania_plan': timezone.localdate() + timedelta(days=smeta.srok_dney or 30),
            }
        form = ObjektForm(initial=initial)

    smety_dlya_vybora = Smeta.objects.filter(brigada=brigada)
    return render(request, 'objekty/create.html', {
        'form': form, 'smeta': smeta, 'smety_dlya_vybora': smety_dlya_vybora,
    })


def _create_etapy_from_smeta(objekt, smeta):
    """Авто-конвертация позиций сметы в этапы графика с равномерными датами."""
    raboty = list(smeta.raboty.all())
    if not raboty:
        return
    total_days = smeta.srok_dney or 30
    per_etap = max(total_days // len(raboty), 1)
    cursor = objekt.data_nachala
    for i, r in enumerate(raboty):
        nachalo = cursor
        okonchanie = nachalo + timedelta(days=per_etap)
        EtapGrafika.objects.create(
            objekt=objekt, smeta_rabota=r, nazvanie=r.nazvanie, edinica=r.edinica,
            plan_objem=r.kolvo, rascenka=r.cena,
            plan_data_nachala=nachalo, plan_data_okonchania=okonchanie, poryadok=i,
        )
        cursor = okonchanie


@login_required
def obekt_detail(request, pk):
    guard = _guard_module(request)
    if guard:
        return guard

    objekt = get_object_or_404(Objekt, pk=pk, brigada=request.user.brigada)
    tab = request.GET.get('tab', 'grafik')

    if request.method == 'POST':
        redirect_tab = _handle_post(request, objekt)
        if redirect_tab:
            return redirect(f"{request.path}?tab={redirect_tab}")

    ai_zaprosy = list(objekt.ai_zaprosy.all())
    context = {
        'objekt': objekt,
        'tab': tab,
        'tab_items': [
            ('grafik', 'График'), ('materialy', 'Материалы'), ('oplata', 'Оплата бригаде'),
            ('rashody', 'Расходы'), ('dengi', 'Деньги от заказчика'), ('ai', 'Спросить прораба'),
        ],
        'etapy': objekt.etapy.all(),
        'materialy': objekt.materialy.select_related('etap').all(),
        'oplaty': objekt.oplaty_montajnikov.all(),
        'rashody': objekt.rashody.all(),
        'dvizhenie': objekt.dvizhenie_deneg.all(),
        'ai_zaprosy': ai_zaprosy,
        'etap_form': EtapGrafikaForm(),
        'material_form': MaterialForm(objekt=objekt),
        'oplata_form': OplataMontajnikaForm(),
        'rashod_form': RashodMesyachnyForm(),
        'dengi_form': DvizhenieDenegForm(objekt=objekt),
        'ai_dostupno': limits.mozhno_sprosit_ai(request.user.brigada),
        'ai_ostatok': _ai_ostatok(request.user.brigada),
        'ai_demo': not ai_assistant.is_configured(),
        'MATERIAL_STATUSY': Material.STATUS_CHOICES,
        'DENGI_STATUSY': DvizhenieDeneg.STATUS_CHOICES,
    }
    return render(request, 'objekty/detail.html', context)


def _ai_ostatok(brigada):
    lim = limits.limit_ai(brigada)
    if lim is None:
        return None  # безлимит
    return max(lim - limits.ai_ispolzovano_v_mesyace(brigada), 0)


def _handle_post(request, objekt):
    """Обрабатывает POST-действия карточки объекта. Возвращает вкладку для redirect."""
    action = request.POST.get('action')

    if action == 'add_etap':
        form = EtapGrafikaForm(request.POST)
        if form.is_valid():
            etap = form.save(commit=False)
            etap.objekt = objekt
            etap.poryadok = objekt.etapy.count()
            etap.save()
            messages.success(request, 'Этап добавлен.')
        else:
            messages.error(request, 'Проверьте поля этапа (даты обязательны).')
        return 'grafik'

    if action == 'set_fact':
        etap = get_object_or_404(EtapGrafika, pk=request.POST.get('etap_id'), objekt=objekt)
        form = FactObjemForm(request.POST, instance=etap)
        if form.is_valid():
            saved = form.save()
            if saved.perezakryt:
                messages.warning(request, f'Внимание: по этапу «{saved.nazvanie}» факт превышает план (перезакрытие).')
            else:
                messages.success(request, 'Факт по этапу обновлён.')
        return 'grafik'

    if action == 'del_etap':
        EtapGrafika.objects.filter(pk=request.POST.get('etap_id'), objekt=objekt).delete()
        messages.success(request, 'Этап удалён.')
        return 'grafik'

    if action == 'add_material':
        form = MaterialForm(request.POST, objekt=objekt)
        if form.is_valid():
            mat = form.save(commit=False)
            mat.objekt = objekt
            mat.save()
            messages.success(request, 'Материал добавлен.')
        else:
            messages.error(request, 'Проверьте поля материала.')
        return 'materialy'

    if action == 'material_status':
        mat = get_object_or_404(Material, pk=request.POST.get('material_id'), objekt=objekt)
        new_status = request.POST.get('status')
        if new_status in dict(Material.STATUS_CHOICES):
            mat.status = new_status
            if new_status == Material.STATUS_ZAKAZAN and not mat.data_zakaza_fakt:
                mat.data_zakaza_fakt = timezone.localdate()
            mat.save()
            messages.success(request, 'Статус материала обновлён.')
        return 'materialy'

    if action == 'del_material':
        Material.objects.filter(pk=request.POST.get('material_id'), objekt=objekt).delete()
        return 'materialy'

    if action == 'add_oplata':
        form = OplataMontajnikaForm(request.POST)
        if form.is_valid():
            op = form.save(commit=False)
            op.objekt = objekt
            # Защита от переплаты (раздел 16 ТЗ): сверхплановая оплата — только с флагом
            if op.prevyshenie_grafika and not op.oplacheno_sverh_grafika:
                messages.warning(request, 'Факт превышает план месяца. Оплата ограничена плановым объёмом — '
                                          'для оплаты сверх графика отметьте соответствующую галочку.')
            op.save()
            messages.success(request, 'Запись по оплате добавлена.')
        else:
            messages.error(request, 'Проверьте поля оплаты.')
        return 'oplata'

    if action == 'del_oplata':
        OplataMontajnika.objects.filter(pk=request.POST.get('oplata_id'), objekt=objekt).delete()
        return 'oplata'

    if action == 'add_rashod':
        form = RashodMesyachnyForm(request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            r.objekt = objekt
            r.save()
            messages.success(request, 'Расходы за месяц добавлены.')
        else:
            messages.error(request, 'Проверьте поля расходов.')
        return 'rashody'

    if action == 'del_rashod':
        RashodMesyachny.objects.filter(pk=request.POST.get('rashod_id'), objekt=objekt).delete()
        return 'rashody'

    if action == 'add_dengi':
        form = DvizhenieDenegForm(request.POST, objekt=objekt)
        if form.is_valid():
            d = form.save(commit=False)
            d.objekt = objekt
            d.save()
            messages.success(request, 'Начисление добавлено.')
        else:
            messages.error(request, 'Проверьте поля начисления.')
        return 'dengi'

    if action == 'dengi_status':
        d = get_object_or_404(DvizhenieDeneg, pk=request.POST.get('dengi_id'), objekt=objekt)
        new_status = request.POST.get('status')
        if new_status in dict(DvizhenieDeneg.STATUS_CHOICES):
            d.status = new_status
            if new_status == DvizhenieDeneg.STATUS_POLUCHENO and not d.data_fakt:
                d.data_fakt = timezone.localdate()
            d.save()
            messages.success(request, 'Статус оплаты обновлён.')
        return 'dengi'

    if action == 'del_dengi':
        DvizhenieDeneg.objects.filter(pk=request.POST.get('dengi_id'), objekt=objekt).delete()
        return 'dengi'

    if action == 'set_status':
        new_status = request.POST.get('status')
        if new_status in dict(Objekt.STATUS_CHOICES):
            objekt.status = new_status
            objekt.save(update_fields=['status'])
            messages.success(request, 'Статус объекта обновлён.')
        return 'grafik'

    if action == 'ask_ai':
        if not limits.mozhno_sprosit_ai(request.user.brigada):
            messages.warning(request, 'Исчерпан месячный лимит запросов к AI-ассистенту по вашему тарифу.')
            return 'ai'
        vopros = (request.POST.get('vopros') or '').strip()
        if vopros:
            otvet, demo = ai_assistant.ask(objekt, vopros)
            AiZapros.objects.create(objekt=objekt, vopros=vopros, otvet=otvet, demo_rezhim=demo)
        return 'ai'

    return 'grafik'
