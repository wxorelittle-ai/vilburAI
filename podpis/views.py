from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from billing import limits as tarif_limits
from core.utils import klientskiy_ip
from documents.models import Dokument
from . import sms
from .models import PodpisZakazchika


def _pep_dostupna(brigada) -> bool:
    """ПЭП — тарифы «Бригадир» и «PRO» (раздел 5 ТЗ). Выводим из тарифной сетки."""
    return tarif_limits.dostupen(brigada, 'pep')


@login_required
def zaprosit_podpis(request, dokument_pk):
    """Владелец инициирует подписание документа заказчиком: создаёт ссылку ПЭП."""
    dokument = get_object_or_404(Dokument, pk=dokument_pk, brigada=request.user.brigada)
    if not _pep_dostupna(request.user.brigada):
        messages.warning(request, 'Электронная подпись доступна на тарифах «Бригадир» и «PRO».')
        return redirect('billing:plans')

    podpis = dokument.podpisi.exclude(status=PodpisZakazchika.STATUS_PODPISANO).first()
    if not podpis:
        podpis = PodpisZakazchika.objects.create(dokument=dokument)

    ssylka = request.build_absolute_uri(f'/sign/{podpis.token}/')
    return render(request, 'podpis/ssylka.html', {
        'dokument': dokument, 'podpis': podpis, 'ssylka': ssylka,
    })


def sign_page(request, token):
    """Публичная страница подписания (без авторизации)."""
    podpis = get_object_or_404(PodpisZakazchika, token=token)
    dokument = podpis.dokument
    demo_kod = None
    kod_zaproshen = bool(podpis.kod_sms_hash)

    if request.method == 'POST' and not podpis.podpisano:
        action = request.POST.get('action')

        if action == 'request_code':
            telefon = (request.POST.get('telefon') or '').strip()
            soglasie = request.POST.get('soglasie') == 'on'
            if not soglasie:
                messages.error(request, 'Подтвердите согласие с условиями договора.')
            elif len(telefon) < 10:
                messages.error(request, 'Укажите корректный номер телефона.')
            else:
                podpis.telefon = telefon
                podpis.save(update_fields=['telefon'])
                kod = PodpisZakazchika.sgenerirovat_kod()
                podpis.zapisat_kod(kod)
                status, kod_dlya_pokaza = sms.otpravit_kod(telefon, kod)

                if status == sms.DEMO:
                    kod_zaproshen = True
                    demo_kod = kod_dlya_pokaza  # показываем на экране только в демо
                    messages.info(request, 'Демо-режим: СМС-шлюз не настроен — код показан ниже.')
                elif status == sms.OTPRAVLENO:
                    kod_zaproshen = True
                    messages.info(request, 'Код отправлен на указанный номер.')
                else:
                    # Боевой режим, но шлюз не ответил. Код не раскрываем — иначе
                    # подписать смог бы любой, у кого есть ссылка.
                    kod_zaproshen = False
                    messages.error(request, 'Не удалось отправить СМС. Попробуйте ещё раз через минуту.')

        elif action == 'confirm':
            kod = (request.POST.get('kod') or '').strip()
            if podpis.proverit_kod(kod):
                podpis.podpisat(telefon=podpis.telefon, ip=klientskiy_ip(request))
                messages.success(request, 'Документ подписан. Спасибо!')
                return redirect('podpis:sign', token=token)
            else:
                messages.error(request, 'Неверный код. Проверьте и попробуйте снова.')
                kod_zaproshen = True

    return render(request, 'podpis/sign.html', {
        'podpis': podpis, 'dokument': dokument, 'brigada': dokument.brigada,
        'kod_zaproshen': kod_zaproshen, 'demo_kod': demo_kod,
    })
