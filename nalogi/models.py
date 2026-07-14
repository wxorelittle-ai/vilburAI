"""
Модуль D — Налоги и чеки ФНС (Addendum №1 ТЗ, разделы 4.6 / «Модуль D»).

Самозанятые обязаны пробивать чек на каждый аванс (ФНС «Мой налог»). Здесь:
- ChekFNS — чек по доходу с автозаполнением из документа;
- NalogOtchet — месячная сводка доход/расход/налог (4% с физлиц, 6% с ИП/юрлиц).

Без ключа ФНС (FNS_API_KEY) работает демо-режим (см. nalogi/fns.py).
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils import timezone


def money(v) -> Decimal:
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class ChekFNS(models.Model):
    STATUS_SOZDAN = 'sozdan'
    STATUS_OTPRAVLEN = 'otpravlen'
    STATUS_OSHIBKA = 'oshibka'
    STATUS_CHOICES = [
        (STATUS_SOZDAN, 'Создан'),
        (STATUS_OTPRAVLEN, 'Пробит и отправлен'),
        (STATUS_OSHIBKA, 'Ошибка'),
    ]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='cheki', verbose_name='Бригада')
    dokument = models.ForeignKey('documents.Dokument', null=True, blank=True, on_delete=models.SET_NULL, related_name='cheki', verbose_name='Документ-основание')
    summa = models.DecimalField('Сумма, ₽', max_digits=12, decimal_places=2)
    naznachenie = models.CharField('Назначение', max_length=255)
    telefon_zakazchika = models.CharField('Телефон заказчика', max_length=20, blank=True)
    email_zakazchika = models.EmailField('Email заказчика', blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_SOZDAN)
    fns_id = models.CharField('ID чека в ФНС', max_length=100, blank=True)
    ssylka = models.URLField('Ссылка на чек', blank=True)
    demo_rezhim = models.BooleanField('Демо-режим', default=False)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Чек ФНС'
        verbose_name_plural = 'Чеки ФНС'
        ordering = ['-data']

    def __str__(self):
        return f'Чек {self.summa} ₽ — {self.get_status_display()}'


class NalogOtchet(models.Model):
    STATUS_OPLACHEN = 'oplachen'
    STATUS_ZADOLZHENNOST = 'zadolzhennost'
    STATUS_CHOICES = [
        (STATUS_OPLACHEN, 'Оплачен'),
        (STATUS_ZADOLZHENNOST, 'Задолженность'),
    ]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='nalog_otchety', verbose_name='Бригада')
    god = models.PositiveSmallIntegerField('Год')
    mesyats = models.PositiveSmallIntegerField('Месяц')
    dohod = models.DecimalField('Доход, ₽', max_digits=12, decimal_places=2, default=0)
    raskhod = models.DecimalField('Расход, ₽', max_digits=12, decimal_places=2, default=0)
    nalog_4 = models.DecimalField('Налог 4% (с физлиц)', max_digits=12, decimal_places=2, default=0)
    nalog_6 = models.DecimalField('Налог 6% (с ИП/юрлиц)', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_ZADOLZHENNOST)

    class Meta:
        verbose_name = 'Налоговый отчёт'
        verbose_name_plural = 'Налоговые отчёты'
        unique_together = [('brigada', 'god', 'mesyats')]
        ordering = ['-god', '-mesyats']

    def __str__(self):
        return f'Налог {self.mesyats:02d}.{self.god} — {self.get_status_display()}'

    @classmethod
    def dohod_za_mesyats(cls, brigada, god, mesyats) -> Decimal:
        agg = (ChekFNS.objects
               .filter(brigada=brigada, status=ChekFNS.STATUS_OTPRAVLEN, data__year=god, data__month=mesyats)
               .aggregate(s=models.Sum('summa')))
        return money(agg['s'] or 0)

    @classmethod
    def svodka_tekushchaya(cls, brigada):
        """Актуальная сводка за текущий месяц (без сохранения): доход и налоги."""
        now = timezone.localtime()
        dohod = cls.dohod_za_mesyats(brigada, now.year, now.month)
        existing = cls.objects.filter(brigada=brigada, god=now.year, mesyats=now.month).first()
        return {
            'god': now.year, 'mesyats': now.month, 'dohod': dohod,
            'nalog_4': money(dohod * Decimal('0.04')),
            'nalog_6': money(dohod * Decimal('0.06')),
            'otchet': existing,
        }
