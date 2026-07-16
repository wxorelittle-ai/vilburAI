from decimal import Decimal, ROUND_HALF_UP

from django.db import models


def dokument_pdf_path(instance, filename):
    return f'dokumenty/{instance.brigada_id}/{instance.tip}/{filename}'


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Dokument(models.Model):
    """
    Документ бригады (раздел 4.2 ТЗ, Модуль A).
    Единая модель на 4 типа документов — специфичные поля используются выборочно
    в зависимости от tip (см. formы в forms.py и шаблоны в templates/documents/pdf/).
    """

    TIP_DOGOVOR = 'dogovor'
    TIP_AKT_VKR = 'akt_vkr'
    TIP_RASPISKA = 'raspiska'
    TIP_AKT_PRIEMKI = 'akt_priemki'

    TIP_CHOICES = [
        (TIP_DOGOVOR, 'Договор подряда'),
        (TIP_AKT_VKR, 'Акт выполненных работ (ВКР)'),
        (TIP_RASPISKA, 'Расписка об авансе'),
        (TIP_AKT_PRIEMKI, 'Акт приёмки этапа'),
    ]

    brigada = models.ForeignKey(
        'core.Brigada', on_delete=models.CASCADE, related_name='dokumenty', verbose_name='Бригада',
    )
    tip = models.CharField('Тип документа', max_length=20, choices=TIP_CHOICES)
    nomer = models.CharField('Номер документа', max_length=30, blank=True)

    # Стороны и объект
    zakazchik = models.CharField('Заказчик (ФИО)', max_length=255)
    zakazchik_telefon = models.CharField('Телефон заказчика', max_length=20, blank=True)
    adres_obekta = models.CharField('Адрес объекта', max_length=500)

    # Деньги и сроки (используются частично, в зависимости от типа)
    summa = models.DecimalField('Сумма договора, ₽', max_digits=12, decimal_places=2, default=0)
    avans_summa = models.DecimalField('Сумма аванса, ₽', max_digits=12, decimal_places=2, default=0, blank=True)
    srok_nachala = models.DateField('Дата начала работ', null=True, blank=True)
    srok_okonchania = models.DateField('Плановая дата окончания', null=True, blank=True)

    # Только для Акта приёмки этапа
    etap_nazvanie = models.CharField('Название этапа', max_length=255, blank=True)
    checklist = models.JSONField('Чек-лист приёмки', default=list, blank=True)

    pdf_file = models.FileField('PDF-файл', upload_to=dokument_pdf_path, blank=True, null=True)
    data_sozdaniya = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ['-data_sozdaniya']
        # список документов бригады — filter(brigada) + order_by(-data_sozdaniya)
        indexes = [models.Index(fields=['brigada', '-data_sozdaniya'])]

    def __str__(self):
        return f'{self.get_tip_display()} №{self.nomer or self.pk} — {self.zakazchik}'

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.nomer:
            prefix = {'dogovor': 'ДП', 'akt_vkr': 'АВ', 'raspiska': 'РА', 'akt_priemki': 'АЭ'}[self.tip]
            self.nomer = f'{prefix}-{self.pk:05d}'
            Dokument.objects.filter(pk=self.pk).update(nomer=self.nomer)

    # --- Договор подряда: поэтапная оплата 30/40/30 (раздел Модуль A ТЗ) -------

    @property
    def avans_platezh(self):
        return money(self.summa * Decimal('0.30'))

    @property
    def promezhutochny_platezh(self):
        return money(self.summa * Decimal('0.40'))

    @property
    def okonchatelny_platezh(self):
        return money(self.summa - self.avans_platezh - self.promezhutochny_platezh)

    # --- Акт ВКР: сумма по позициям --------------------------------------------

    @property
    def itogo_po_poziciyam(self):
        return money(sum((p.summa for p in self.pozicii.all()), Decimal('0.00')))

    DEFAULT_CHECKLIST = [
        'Работы по этапу выполнены в полном объёме, предусмотренном сметой/договором',
        'Использованные материалы соответствуют согласованным маркам и характеристикам',
        'Качество выполненных работ соответствует строительным нормам и правилам (СП/СНиП)',
        'Поверхности и конструкции очищены от строительного мусора',
        'Скрытые работы (при наличии) зафиксированы фотографиями до их закрытия',
        'Отклонений от проектной документации/эскиза не выявлено',
        'Замечания по итогам осмотра отсутствуют либо устранены до подписания акта',
        'Объём выполненных работ подтверждён обеими сторонами визуально на объекте',
        'Заказчик ознакомлен с рекомендациями по эксплуатации выполненных работ',
        'Претензий по объёму, качеству и срокам выполнения этапа на момент подписания не имеется',
    ]


class DokumentPozicia(models.Model):
    """Позиция (строка работ) для Акта ВКР — таблица с автоподсчётом (раздел Модуль A ТЗ)."""

    dokument = models.ForeignKey(Dokument, on_delete=models.CASCADE, related_name='pozicii')
    nazvanie = models.CharField('Наименование работы', max_length=255)
    edinica = models.CharField('Ед. изм.', max_length=20, default='м²')
    kolvo = models.DecimalField('Кол-во', max_digits=10, decimal_places=2, default=0)
    cena = models.DecimalField('Цена за ед., ₽', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Позиция акта'
        verbose_name_plural = 'Позиции акта'

    def __str__(self):
        return self.nazvanie

    @property
    def summa(self):
        return money(self.kolvo * self.cena)
