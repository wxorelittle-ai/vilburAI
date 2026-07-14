from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from documents.models import Dokument
from podpis.models import PodpisZakazchika
from . import wa, telegram
from .models import WhatsAppOtpravka, TelegramUser


def messengers_dostupny(brigada) -> bool:
    return brigada.effective_tarif in ('brigadir', 'pro')


def _guard(request):
    if not messengers_dostupny(request.user.brigada):
        messages.warning(request, 'WhatsApp/Telegram доступны на тарифах «Бригадир» и «PRO».')
        return redirect('billing:plans')
    return None


@login_required
def nastroiki(request):
    guard = _guard(request)
    if guard:
        return guard
    brigada = request.user.brigada
    tg = TelegramUser.dlya_brigady(brigada)
    deep_link = f'https://t.me/{telegram.bot_username()}?start={tg.connect_code}'
    return render(request, 'messengers/nastroiki.html', {
        'tg': tg, 'deep_link': deep_link,
        'tg_demo': not telegram.is_configured(),
        'wa_demo': not wa.is_configured(),
        'wa_otpravki': WhatsAppOtpravka.objects.filter(dokument__brigada=brigada)[:30],
    })


@login_required
def otpravit_wa(request, dokument_pk):
    guard = _guard(request)
    if guard:
        return guard
    dokument = get_object_or_404(Dokument, pk=dokument_pk, brigada=request.user.brigada)
    if request.method != 'POST':
        return redirect('documents:detail', pk=dokument.pk)

    tip = request.POST.get('tip', WhatsAppOtpravka.TIP_DOKUMENT)
    telefon = (request.POST.get('telefon') or dokument.zakazchik_telefon or '').strip()
    if not telefon:
        messages.error(request, 'Укажите телефон получателя.')
        return redirect('documents:detail', pk=dokument.pk)

    if tip == WhatsAppOtpravka.TIP_PODPIS:
        podpis = dokument.podpisi.exclude(status=PodpisZakazchika.STATUS_PODPISANO).first()
        if not podpis:
            podpis = PodpisZakazchika.objects.create(dokument=dokument)
        ssylka = request.build_absolute_uri(f'/sign/{podpis.token}/')
        tekst = f'{dokument.brigada.nazvanie}: подпишите {dokument.get_tip_display()} №{dokument.nomer} — {ssylka}'
    else:
        tekst = (f'{dokument.brigada.nazvanie}: направляем {dokument.get_tip_display()} '
                 f'№{dokument.nomer}. Документ во вложении/по ссылке в личном кабинете.')

    ok, demo, _ = wa.otpravit(dokument, telefon, tip, tekst)
    if ok:
        messages.success(request, 'Отправлено в WhatsApp.' + (' (демо-режим)' if demo else ''))
    else:
        messages.error(request, 'Не удалось отправить через шлюз WhatsApp.')
    return redirect('documents:detail', pk=dokument.pk)
