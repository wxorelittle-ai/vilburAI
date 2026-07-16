from decimal import Decimal, ROUND_HALF_UP

from django.db import models


def money(value) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Raschet(models.Model):
    """
    Калькулятор себестоимости (раздел 4.3 / Модуль C ТЗ).

    Методика расчёта (детализирует список полей из ТЗ конкретной формулой):
    - Трудозатраты = кол-во рабочих × дни × ставка за 1 рабочего в день.
      Ставка не указана явно в перечне полей ТЗ, но необходима для расчёта
      стоимости труда — добавлена как отдельное поле с разумным дефолтом.
    - Постоянные расходы = аренда инструмента + доставка материалов + расходники.
    - Себестоимость = трудозатраты + постоянные расходы.
    - Себестоимость за м² = себестоимость / площадь.
    - Рекомендуемые цены (+30% / +50% прибыли) пересчитываются с учётом налога:
      чтобы после уплаты налога с выручки у бригады осталась заложенная прибыль,
      цена делится на (1 − ставка налога).
    - Точка безубыточности (в днях) — на какой день проекта накопленная выручка
      (по цене +30%, равномерно распределённая по дням) перекроет постоянные
      (предоплаченные) расходы, при условии что дневная выручка выше дневных
      трудозатрат.
    """

    TIP_REMONTA_CHOICES = [
        ('econom', 'Эконом'),
        ('komfort', 'Комфорт'),
        ('premium', 'Премиум'),
    ]
    NALOG_CHOICES = [
        ('4', 'Самозанятый — 4%'),
        ('6', 'ИП УСН доходы — 6%'),
        ('0', 'Наличные — 0%'),
    ]

    # Ориентировочные средние рыночные цены за м² по типу ремонта (раздел Модуль C ТЗ:
    # «сравнение с рыночными ценами по региону»). Упрощённый статичный справочник —
    # полноценная региональная база цен (BazaCen) появится вместе с Модулем B.
    RYNOCHNAYA_CENA_M2 = {
        'econom': Decimal('2500'),
        'komfort': Decimal('4500'),
        'premium': Decimal('8000'),
    }

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='raschety', verbose_name='Бригада')

    ploshad = models.DecimalField('Площадь помещения, м²', max_digits=10, decimal_places=2)
    tip_remonta = models.CharField('Тип ремонта', max_length=10, choices=TIP_REMONTA_CHOICES, default='komfort')
    kolvo_rabochih = models.PositiveSmallIntegerField('Количество рабочих', default=1)
    dni = models.PositiveSmallIntegerField('Срок выполнения, дней', default=1)
    stavka_v_den = models.DecimalField('Оплата 1 рабочему в день, ₽', max_digits=10, decimal_places=2, default=3000)

    arenda = models.DecimalField('Аренда инструмента, ₽', max_digits=10, decimal_places=2, default=0)
    dostavka = models.DecimalField('Доставка материалов, ₽', max_digits=10, decimal_places=2, default=0)
    rashodniki = models.DecimalField('Расходники (перчатки, обеды и т.п.), ₽', max_digits=10, decimal_places=2, default=0)

    nalog = models.CharField('Налоговый режим', max_length=2, choices=NALOG_CHOICES, default='4')

    data = models.DateTimeField('Дата расчёта', auto_now_add=True)

    class Meta:
        verbose_name = 'Расчёт себестоимости'
        verbose_name_plural = 'Расчёты себестоимости'
        ordering = ['-data']
        indexes = [models.Index(fields=['brigada', '-data'])]

    def __str__(self):
        return f'Расчёт от {self.data:%d.%m.%Y} — {self.ploshad} м²'

    # --- Промежуточные суммы -----------------------------------------------

    @property
    def trudozatraty(self) -> Decimal:
        return money(self.kolvo_rabochih * self.dni * self.stavka_v_den)

    @property
    def postoyannye_raskhody(self) -> Decimal:
        return money(self.arenda + self.dostavka + self.rashodniki)

    @property
    def sebestoimost_obshaya(self) -> Decimal:
        return money(self.trudozatraty + self.postoyannye_raskhody)

    @property
    def sebestoimost_m2(self) -> Decimal:
        if not self.ploshad:
            return Decimal('0.00')
        return money(self.sebestoimost_obshaya / self.ploshad)

    @property
    def nalog_stavka(self) -> Decimal:
        return Decimal(self.nalog) / Decimal('100')

    def _cena_s_pribylyu(self, margin: Decimal) -> Decimal:
        baza = self.sebestoimost_obshaya * (Decimal('1') + margin)
        stavka = self.nalog_stavka
        if stavka >= Decimal('1'):
            return money(baza)
        return money(baza / (Decimal('1') - stavka))

    @property
    def cena_30(self) -> Decimal:
        """Рекомендуемая цена всего объёма работ с прибылью 30% (с учётом налога)."""
        return self._cena_s_pribylyu(Decimal('0.30'))

    @property
    def cena_50(self) -> Decimal:
        """Рекомендуемая цена всего объёма работ с прибылью 50% (с учётом налога)."""
        return self._cena_s_pribylyu(Decimal('0.50'))

    @property
    def cena_30_m2(self) -> Decimal:
        if not self.ploshad:
            return Decimal('0.00')
        return money(self.cena_30 / self.ploshad)

    @property
    def cena_50_m2(self) -> Decimal:
        if not self.ploshad:
            return Decimal('0.00')
        return money(self.cena_50 / self.ploshad)

    @property
    def tochka_bezubytochnosti_dney(self):
        """Через сколько дней накопленная выручка (по цене +30%) перекроет
        постоянные расходы. None, если выручка не превышает дневные трудозатраты."""
        if self.dni <= 0:
            return None
        dnevnaya_vyruchka = self.cena_30 / self.dni
        dnevnye_trudozatraty = self.kolvo_rabochih * self.stavka_v_den
        razница = dnevnaya_vyruchka - dnevnye_trudozatraty
        if razница <= 0:
            return None
        dney = self.postoyannye_raskhody / razница
        return int(dney.to_integral_value(rounding=ROUND_HALF_UP))

    # --- Сравнение с рынком ---------------------------------------------------

    @property
    def rynochnaya_cena_m2(self) -> Decimal:
        return self.RYNOCHNAYA_CENA_M2.get(self.tip_remonta, Decimal('0'))

    @property
    def otklonenie_ot_rynka_procent(self):
        """Положительное значение — рекомендуемая цена ниже рынка на N%."""
        rynok = self.rynochnaya_cena_m2
        if not rynok:
            return None
        otklonenie = (rynok - self.cena_30_m2) / rynok * Decimal('100')
        return int(otklonenie.to_integral_value(rounding=ROUND_HALF_UP))
