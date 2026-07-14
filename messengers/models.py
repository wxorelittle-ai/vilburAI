"""
Модуль F — WhatsApp / Telegram (Addendum №1 ТЗ, разделы 4.7 / «Модуль F»).

- WhatsAppOtpravka: отправки документов и ссылок на подпись заказчику;
- TelegramUser: привязка Telegram-аккаунта бригады к боту уведомлений.

Внешние каналы работают в демо-режиме без ключей (WHATSAPP_API_KEY / TELEGRAM_BOT_TOKEN).
"""

import secrets

from django.db import models


class WhatsAppOtpravka(models.Model):
    TIP_DOKUMENT = 'dokument'
    TIP_PODPIS = 'podpis'
    TIP_NAPOMINANIE = 'napominanie'
    TIP_CHOICES = [
        (TIP_DOKUMENT, 'Документ'),
        (TIP_PODPIS, 'Ссылка на подпись'),
        (TIP_NAPOMINANIE, 'Напоминание'),
    ]

    STATUS_OTPRAVLENO = 'otpravleno'
    STATUS_DOSTAVLENO = 'dostavleno'
    STATUS_PROCHITANO = 'prochitano'
    STATUS_OSHIBKA = 'oshibka'
    STATUS_CHOICES = [
        (STATUS_OTPRAVLENO, 'Отправлено'),
        (STATUS_DOSTAVLENO, 'Доставлено'),
        (STATUS_PROCHITANO, 'Прочитано'),
        (STATUS_OSHIBKA, 'Ошибка'),
    ]

    dokument = models.ForeignKey('documents.Dokument', on_delete=models.CASCADE, related_name='wa_otpravki', verbose_name='Документ')
    telefon = models.CharField('Телефон получателя', max_length=20)
    tip = models.CharField('Тип', max_length=20, choices=TIP_CHOICES, default=TIP_DOKUMENT)
    tekst = models.CharField('Текст сообщения', max_length=500, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OTPRAVLENO)
    demo_rezhim = models.BooleanField('Демо-режим', default=False)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Отправка в WhatsApp'
        verbose_name_plural = 'Отправки в WhatsApp'
        ordering = ['-data']

    def __str__(self):
        return f'{self.telefon} — {self.get_tip_display()}'


class TelegramUser(models.Model):
    STATUS_OZHIDAET = 'ozhidaet'
    STATUS_SVYAZAN = 'svyazan'
    STATUS_CHOICES = [(STATUS_OZHIDAET, 'Ожидает привязки'), (STATUS_SVYAZAN, 'Привязан')]

    brigada = models.OneToOneField('core.Brigada', on_delete=models.CASCADE, related_name='telegram', verbose_name='Бригада')
    connect_code = models.SlugField('Код привязки', max_length=16, unique=True, blank=True)
    telegram_id = models.BigIntegerField('Telegram ID', null=True, blank=True, unique=True)
    username = models.CharField('Username', max_length=100, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OZHIDAET)
    data = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Telegram-аккаунт'
        verbose_name_plural = 'Telegram-аккаунты'

    def __str__(self):
        return f'{self.brigada.nazvanie} — {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.connect_code:
            self.connect_code = secrets.token_urlsafe(8).replace('_', '').replace('-', '')[:12]
        super().save(*args, **kwargs)

    @property
    def svyazan(self) -> bool:
        return self.status == self.STATUS_SVYAZAN

    @classmethod
    def dlya_brigady(cls, brigada):
        obj, _ = cls.objects.get_or_create(brigada=brigada)
        return obj
