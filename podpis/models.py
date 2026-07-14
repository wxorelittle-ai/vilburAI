"""
Модуль I — Простая электронная подпись (ПЭП), Addendum №1 ТЗ (разделы 4.7, «Модуль I»).

Заказчик получает уникальную ссылку /sign/<token>/, читает документ, ставит галочку
согласия и подтверждает подпись СМС-кодом. Фиксируются дата, IP, телефон и SHA-256-хеш
документа. Юридическая основа — ПЭП по 63-ФЗ для бытовых договоров.

Безопасность (раздел 8/16 ТЗ): СМС-код хранится ТОЛЬКО в хешированном виде
(Django-хешер), в открытом виде не сохраняется никогда.
"""

import hashlib
import secrets

from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone


class PodpisZakazchika(models.Model):
    STATUS_OZHIDAET = 'ozhidaet'
    STATUS_PODPISANO = 'podpisano'
    STATUS_OTKLONENO = 'otkloneno'
    STATUS_CHOICES = [
        (STATUS_OZHIDAET, 'Ожидает подписания'),
        (STATUS_PODPISANO, 'Подписано'),
        (STATUS_OTKLONENO, 'Отклонено'),
    ]

    dokument = models.ForeignKey('documents.Dokument', on_delete=models.CASCADE, related_name='podpisi', verbose_name='Документ')
    token = models.SlugField('Токен ссылки', max_length=32, unique=True, blank=True)
    telefon = models.CharField('Телефон подписанта', max_length=20, blank=True)
    ip_adres = models.GenericIPAddressField('IP подписанта', null=True, blank=True)
    kod_sms_hash = models.CharField('Хеш СМС-кода', max_length=255, blank=True)
    soglasie = models.BooleanField('Согласие с условиями', default=False)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OZHIDAET)
    doc_hash = models.CharField('SHA-256 документа', max_length=64, blank=True)
    data_sozdaniya = models.DateTimeField('Создано', auto_now_add=True)
    data_podpisi = models.DateTimeField('Дата подписи', null=True, blank=True)

    class Meta:
        verbose_name = 'Подпись заказчика (ПЭП)'
        verbose_name_plural = 'Подписи заказчиков (ПЭП)'
        ordering = ['-data_sozdaniya']

    def __str__(self):
        return f'ПЭП {self.dokument.nomer} — {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(12).replace('_', '').replace('-', '')[:16]
        super().save(*args, **kwargs)

    # --- СМС-код (хранится только хешем) --------------------------------------

    @staticmethod
    def sgenerirovat_kod() -> str:
        return f'{secrets.randbelow(10**6):06d}'

    def zapisat_kod(self, kod: str):
        self.kod_sms_hash = make_password(kod)
        self.save(update_fields=['kod_sms_hash'])

    def proverit_kod(self, kod: str) -> bool:
        return bool(self.kod_sms_hash) and check_password(kod, self.kod_sms_hash)

    # --- Хеш документа --------------------------------------------------------

    def vychislit_doc_hash(self) -> str:
        h = hashlib.sha256()
        if self.dokument.pdf_file:
            try:
                with self.dokument.pdf_file.open('rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        h.update(chunk)
                return h.hexdigest()
            except (FileNotFoundError, ValueError):
                pass
        # запасной вариант: хеш ключевых полей документа
        d = self.dokument
        h.update(f'{d.nomer}|{d.tip}|{d.zakazchik}|{d.adres_obekta}|{d.summa}'.encode('utf-8'))
        return h.hexdigest()

    def podpisat(self, telefon: str, ip: str):
        self.telefon = telefon
        self.ip_adres = ip
        self.soglasie = True
        self.status = self.STATUS_PODPISANO
        self.data_podpisi = timezone.now()
        self.doc_hash = self.vychislit_doc_hash()
        self.kod_sms_hash = ''  # код больше не нужен — стираем даже хеш
        self.save()

    @property
    def podpisano(self) -> bool:
        return self.status == self.STATUS_PODPISANO
