from django.db import models
from django.utils import timezone


class Platezh(models.Model):
    """Платёж по подписке (раздел 4.5 ТЗ)."""

    STATUS_OZHIDAET = 'ozhidaet'
    STATUS_OPLACHEN = 'oplachen'
    STATUS_VOZVRAT = 'vozvrat'
    STATUS_OTMENEN = 'otmenen'

    STATUS_CHOICES = [
        (STATUS_OZHIDAET, 'Ожидает оплаты'),
        (STATUS_OPLACHEN, 'Оплачен'),
        (STATUS_VOZVRAT, 'Возврат'),
        (STATUS_OTMENEN, 'Отменён'),
    ]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='platezhi', verbose_name='Бригада')
    summa = models.DecimalField('Сумма, ₽', max_digits=10, decimal_places=2)
    tarif = models.CharField('Тариф', max_length=20, choices=[
        ('samozanyaty', 'Самозанятый'), ('brigadir', 'Бригадир'), ('pro', 'PRO'),
    ])
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OZHIDAET)
    data = models.DateTimeField('Дата', auto_now_add=True)
    yookassa_id = models.CharField('ID платежа в ЮKassa', max_length=100, blank=True)
    demo_rezhim = models.BooleanField(
        'Тестовый режим (без ключей ЮKassa)', default=False,
        help_text='Платёж симулирован локально, реальных денег не было',
    )

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-data']
        indexes = [
            models.Index(fields=['brigada', '-data']),
            models.Index(fields=['yookassa_id']),   # поиск платежа при обработке вебхука
        ]

    def __str__(self):
        return f'{self.brigada.nazvanie} — {self.tarif} — {self.summa} ₽ ({self.get_status_display()})'


class LimitTracker(models.Model):
    """
    Счётчики использования по месяцам (раздел 4.5 ТЗ). Обновляются сигналами
    post_save при создании документа/расчёта/сметы (см. billing/signals.py) —
    это быстрее, чем пересчитывать COUNT(*) по таблицам документов при каждой проверке.
    """

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='limit_trackers', verbose_name='Бригада')
    god = models.PositiveSmallIntegerField('Год')
    mesyats = models.PositiveSmallIntegerField('Месяц')

    dokumenty_ispolzovano = models.PositiveIntegerField('Использовано документов', default=0)
    raschety_ispolzovano = models.PositiveIntegerField('Использовано расчётов', default=0)
    smety_ispolzovano = models.PositiveIntegerField('Использовано смет', default=0)

    class Meta:
        verbose_name = 'Счётчик лимитов'
        verbose_name_plural = 'Счётчики лимитов'
        unique_together = [('brigada', 'god', 'mesyats')]

    def __str__(self):
        return f'{self.brigada.nazvanie} — {self.mesyats:02d}.{self.god}'

    @classmethod
    def get_or_create_current(cls, brigada):
        now = timezone.localtime()
        obj, _ = cls.objects.get_or_create(brigada=brigada, god=now.year, mesyats=now.month)
        return obj

    @classmethod
    def increment(cls, brigada, field_name):
        from django.db.models import F
        tracker = cls.get_or_create_current(brigada)
        cls.objects.filter(pk=tracker.pk).update(**{field_name: F(field_name) + 1})
