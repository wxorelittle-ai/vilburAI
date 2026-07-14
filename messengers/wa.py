"""
Отправка в WhatsApp (раздел 6.6 ТЗ). Без ключа (WHATSAPP_API_KEY) — демо-режим:
сообщение помечается отправленным локально. С ключом — через облачный шлюз (Wazzup/edna).
"""

from django.conf import settings

from .models import WhatsAppOtpravka


def is_configured() -> bool:
    return bool(getattr(settings, 'WHATSAPP_API_KEY', ''))


def otpravit(dokument, telefon, tip, tekst):
    """Создаёт запись отправки и «отправляет». Возвращает (ok, demo, otpravka)."""
    demo = not is_configured()
    otpravka = WhatsAppOtpravka(
        dokument=dokument, telefon=telefon, tip=tip, tekst=tekst[:500],
        status=WhatsAppOtpravka.STATUS_OTPRAVLENO, demo_rezhim=demo,
    )
    if not demo:
        try:
            import requests
            requests.post(
                'https://api.wazzup24.com/v3/message',
                headers={'Authorization': f'Bearer {settings.WHATSAPP_API_KEY}'},
                json={'chatType': 'whatsapp', 'chatId': telefon, 'text': tekst},
                timeout=15,
            )
        except Exception:  # noqa: BLE001 — не роняем UI из-за шлюза
            otpravka.status = WhatsAppOtpravka.STATUS_OSHIBKA
    otpravka.save()
    return otpravka.status != WhatsAppOtpravka.STATUS_OSHIBKA, demo, otpravka
