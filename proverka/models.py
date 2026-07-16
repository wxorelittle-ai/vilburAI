"""
Модуль E — Проверка заказчика (Addendum №1 ТЗ, разделы 4.6 / «Модуль E»).

Проверка по ИНН (юрлицо: статус, руководитель, адрес, арбитражные дела) и по телефону
(физлицо: внутренняя накопительная база инцидентов неоплаты). Риск-скоринг и рекомендация
по размеру аванса. Внешние источники (Контур/СПАРК, kad.arbitr.ru) — в демо-режиме.
"""

from django.db import models


class ChyornySpisok(models.Model):
    """Внутренняя накопительная база инцидентов неоплаты (народный чёрный список)."""

    ISTOCHNIK_CHOICES = [
        ('narod', 'Жалобы бригад'),
        ('arbitr', 'Арбитражные дела'),
        ('fns', 'ФНС / реестры'),
    ]

    telefon = models.CharField('Телефон', max_length=20, blank=True, db_index=True)
    inn = models.CharField('ИНН', max_length=12, blank=True, db_index=True)
    prichina = models.CharField('Причина', max_length=255)
    istochnik = models.CharField('Источник', max_length=20, choices=ISTOCHNIK_CHOICES, default='narod')
    kolvo_zhalob = models.PositiveIntegerField('Количество жалоб', default=1)
    data = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись чёрного списка'
        verbose_name_plural = 'Чёрный список'
        ordering = ['-kolvo_zhalob']

    def __str__(self):
        return self.telefon or self.inn or 'запись'


class ProverkaZakazchika(models.Model):
    TIP_INN = 'inn'
    TIP_TELEFON = 'telefon'
    TIP_CHOICES = [(TIP_INN, 'По ИНН (юрлицо/ИП)'), (TIP_TELEFON, 'По телефону (физлицо)')]

    RISK_NIZKY = 'nizky'
    RISK_SREDNY = 'sredny'
    RISK_VYSOKY = 'vysoky'
    RISK_CHOICES = [
        (RISK_NIZKY, 'Низкий'),
        (RISK_SREDNY, 'Средний'),
        (RISK_VYSOKY, 'Высокий'),
    ]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='proverki', verbose_name='Бригада')
    tip_poiska = models.CharField('Тип проверки', max_length=10, choices=TIP_CHOICES)
    znachenie = models.CharField('ИНН / телефон', max_length=30)
    status_riska = models.CharField('Уровень риска', max_length=10, choices=RISK_CHOICES)
    prichina = models.CharField('Обоснование', max_length=255, blank=True)
    detali = models.JSONField('Детали', default=dict, blank=True)
    demo_rezhim = models.BooleanField('Демо-режим', default=False)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Проверка заказчика'
        verbose_name_plural = 'Проверки заказчиков'
        ordering = ['-data']
        indexes = [models.Index(fields=['brigada', '-data'])]

    def __str__(self):
        return f'{self.znachenie} — {self.get_status_riska_display()}'

    @property
    def rekomendaciya(self) -> str:
        return {
            self.RISK_NIZKY: 'Риск низкий — можно работать. Аванс до 30–50%, договор обязателен.',
            self.RISK_SREDNY: 'Риск средний — аванс не более 30%, только по договору с ПЭП и поэтапной оплатой.',
            self.RISK_VYSOKY: 'Риск высокий — работать только по 100% предоплате поэтапно либо отказаться.',
        }.get(self.status_riska, '')

    @property
    def risk_tone(self) -> str:
        return {self.RISK_NIZKY: 'green', self.RISK_SREDNY: 'amber', self.RISK_VYSOKY: 'red'}.get(self.status_riska, 'steel')
