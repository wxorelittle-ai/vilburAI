"""
Модуль J — Контроль объекта (Addendum №2 ТЗ, раздел 4.8).

Закрывает жизнь объекта от старта до сдачи: график работ, материалы с расчётом
крайней даты заказа, оплата монтажникам с защитой от переплаты, месячные расходы,
движение денег от заказчика и кассовый разрыв. Плюс сводные показатели для
дашборда и JSON-контекст для AI-ассистента прораба (см. ai_assistant.py).

Ключевые правила ТЗ (раздел 16, Addendum №2), реализованные тут:
- дата заказа материала считается ОТ ДАТЫ НАЧАЛА этапа (не от окончания);
- монтажнику нельзя платить сверх планового объёма месяца без явного флага;
- этап не помечается выполненным сверх темпа автоматически — только ввод факта.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


def money(value) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Objekt(models.Model):
    """Карточка объекта. Создаётся вручную или автоматически из подписанной сметы."""

    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_PAUSED = 'paused'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'В работе'),
        (STATUS_COMPLETED, 'Сдан'),
        (STATUS_PAUSED, 'Приостановлен'),
    ]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='obekty', verbose_name='Бригада')
    smeta = models.ForeignKey('smety.Smeta', null=True, blank=True, on_delete=models.SET_NULL, related_name='obekty', verbose_name='Смета-источник')

    nazvanie = models.CharField('Название объекта', max_length=255)
    adres = models.CharField('Адрес', max_length=500, blank=True)
    zakazchik = models.CharField('Заказчик', max_length=255, blank=True)
    master_otvetstvenny = models.CharField('Ответственный мастер', max_length=255, blank=True)

    data_nachala = models.DateField('Дата начала')
    data_okonchania_plan = models.DateField('Плановая дата окончания')
    summa_dogovora = models.DecimalField('Сумма договора, ₽', max_digits=12, decimal_places=2, default=0)

    avans_procent = models.PositiveSmallIntegerField('Аванс, %', default=30)
    srok_oplaty_posle_akta_dney = models.PositiveSmallIntegerField('Срок оплаты после акта, дней', default=10)
    garantiynoe_uderzhanie_procent = models.PositiveSmallIntegerField('Гарантийное удержание, %', default=5)
    srok_vozvrata_garantii_dney = models.PositiveSmallIntegerField('Срок возврата гарантийного удержания, дней', default=365)

    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    data_sozdaniya = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Объект'
        verbose_name_plural = 'Объекты'
        ordering = ['-data_sozdaniya']

    def __str__(self):
        return self.nazvanie

    # --- Готовность и график ---------------------------------------------------

    @cached_property
    def plan_objem_itogo(self) -> Decimal:
        return money(sum((e.plan_objem for e in self.etapy.all()), Decimal('0')))

    @cached_property
    def fact_objem_itogo(self) -> Decimal:
        return money(sum((e.fact_objem for e in self.etapy.all()), Decimal('0')))

    @cached_property
    def procent_gotovnosti(self) -> int:
        """% готовности как средневзвешенный по плановым объёмам этапов."""
        plan = self.plan_objem_itogo
        if not plan:
            return 0
        return int((self.fact_objem_itogo / plan * 100).to_integral_value(rounding=ROUND_HALF_UP))

    @cached_property
    def otstaet_ot_grafika(self) -> bool:
        return any(e.status_temp == 'otstavanie' for e in self.etapy.all())

    # --- Материалы к заказу ----------------------------------------------------

    def materialy_k_zakazu(self, dney=7):
        """Ещё не заказанные материалы, крайняя дата которых наступит в ближайшие
        N дней либо уже прошла. Уже заказанные/в пути/на объекте — не считаются."""
        today = timezone.localdate()
        gorizont = today + timedelta(days=dney)
        result = []
        for m in self.materialy.all():
            if m.status != Material.STATUS_NE_ZAKAZAN:
                continue
            kraynyaya = m.data_zakaza_kraynyaya
            if kraynyaya and kraynyaya <= gorizont:
                result.append(m)
        return result

    @cached_property
    def est_prosrochennye_materialy(self) -> bool:
        return any(m.prosrocheno for m in self.materialy.all())

    # --- Деньги и кассовый разрыв ----------------------------------------------

    @cached_property
    def prihod_poluchen(self) -> Decimal:
        return money(sum((d.summa_nachislenie for d in self.dvizhenie_deneg.all() if d.status == DvizhenieDeneg.STATUS_POLUCHENO), Decimal('0')))

    @cached_property
    def prihod_ozhidaetsya(self) -> Decimal:
        return money(sum((d.summa_nachislenie for d in self.dvizhenie_deneg.all() if d.status != DvizhenieDeneg.STATUS_POLUCHENO), Decimal('0')))

    @cached_property
    def rashod_itogo(self) -> Decimal:
        rashody = sum((r.itogo for r in self.rashody.all()), Decimal('0'))
        oplaty = sum((o.summa_oplacheno for o in self.oplaty_montajnikov.all()), Decimal('0'))
        return money(rashody + oplaty)

    @cached_property
    def kassovy_razryv(self) -> Decimal:
        """Получено от заказчика минус потрачено. Отрицательное — кассовый разрыв."""
        return money(self.prihod_poluchen - self.rashod_itogo)

    @cached_property
    def est_kassovy_razryv(self) -> bool:
        return self.kassovy_razryv < 0

    # --- Переплата монтажникам -------------------------------------------------

    @cached_property
    def est_risk_pereplaty(self) -> bool:
        return any(o.prevyshenie_grafika and not o.oplacheno_sverh_grafika for o in self.oplaty_montajnikov.all())

    # --- Флаги для блока «⚠ Требует внимания» -----------------------------------

    @cached_property
    def krasnye_flagi(self):
        """Красные флаги (раздел 7.6 ТЗ): просрочка материала и кассовый разрыв.
        Отставание от графика — это ЖЁЛТЫЙ уровень (см. otstaet_ot_grafika), сюда не входит."""
        flagi = []
        prosrocheno = [m for m in self.materialy.all() if m.prosrocheno]
        if prosrocheno:
            flagi.append(f'Просрочен заказ материалов: {len(prosrocheno)} шт.')
        skoro = self.materialy_k_zakazu(7)
        skoro = [m for m in skoro if not m.prosrocheno]
        if skoro:
            flagi.append(f'Заказать материалы в ближайшие 7 дней: {len(skoro)} шт.')
        if self.est_kassovy_razryv:
            flagi.append(f'Кассовый разрыв: {self.kassovy_razryv} ₽')
        if self.est_risk_pereplaty:
            flagi.append('Риск переплаты монтажнику сверх планового объёма')
        return flagi

    @cached_property
    def zhyoltye_flagi(self):
        """Жёлтый уровень (раздел 7.6 ТЗ): отставание от графика."""
        flagi = []
        otstayushchie = [e for e in self.etapy.all() if e.status_temp == 'otstavanie']
        if otstayushchie:
            flagi.append('Отставание от графика: этапов — %d' % len(otstayushchie))
        return flagi


class EtapGrafika(models.Model):
    """Этап графика работ. Автоматически создаётся из позиций сметы."""

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name='etapy', verbose_name='Объект')
    smeta_rabota = models.ForeignKey('smety.SmetaRabota', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    nazvanie = models.CharField('Этап / работа', max_length=255)
    edinica = models.CharField('Ед. изм.', max_length=20, default='м²')
    plan_objem = models.DecimalField('План, объём', max_digits=10, decimal_places=2, default=0)
    fact_objem = models.DecimalField('Факт, объём', max_digits=10, decimal_places=2, default=0)
    rascenka = models.DecimalField('Расценка за ед., ₽', max_digits=10, decimal_places=2, default=0)
    plan_data_nachala = models.DateField('План: начало')
    plan_data_okonchania = models.DateField('План: окончание')
    poryadok = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Этап графика'
        verbose_name_plural = 'График работ'
        ordering = ['poryadok', 'plan_data_nachala', 'id']

    def __str__(self):
        return self.nazvanie

    @cached_property
    def procent(self) -> int:
        if not self.plan_objem:
            return 0
        return int((self.fact_objem / self.plan_objem * 100).to_integral_value(rounding=ROUND_HALF_UP))

    @cached_property
    def perezakryt(self) -> bool:
        """Факт превышает план — предупреждение о перезакрытии."""
        return self.fact_objem > self.plan_objem

    @cached_property
    def status_temp(self) -> str:
        """'opustil' по темпу: opережение / v_grafike / otstavanie / gotov."""
        if self.plan_objem and self.fact_objem >= self.plan_objem:
            return 'gotov'
        today = timezone.localdate()
        if today < self.plan_data_nachala:
            return 'v_grafike'
        total_days = (self.plan_data_okonchania - self.plan_data_nachala).days or 1
        proshlo = (today - self.plan_data_nachala).days
        ozhidaemy_procent = min(max(proshlo / total_days, 0), 1) * 100
        if self.procent + 5 < ozhidaemy_procent:
            return 'otstavanie'
        if self.procent > ozhidaemy_procent + 15:
            return 'operezhenie'
        return 'v_grafike'

    @cached_property
    def status_temp_label(self) -> str:
        return {
            'gotov': 'Выполнен',
            'v_grafike': 'По графику',
            'otstavanie': 'Отставание',
            'operezhenie': 'Опережение',
        }.get(self.status_temp, '—')


class Material(models.Model):
    """Материал, привязанный к этапу. Крайняя дата заказа считается от начала этапа."""

    STATUS_NE_ZAKAZAN = 'ne_zakazan'
    STATUS_ZAKAZAN = 'zakazan'
    STATUS_V_PUTI = 'v_puti'
    STATUS_NA_OBEKTE = 'na_obekte'
    STATUS_CHOICES = [
        (STATUS_NE_ZAKAZAN, 'Не заказан'),
        (STATUS_ZAKAZAN, 'Заказан'),
        (STATUS_V_PUTI, 'В пути'),
        (STATUS_NA_OBEKTE, 'На объекте'),
    ]

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name='materialy', verbose_name='Объект')
    etap = models.ForeignKey(EtapGrafika, on_delete=models.CASCADE, related_name='materialy', verbose_name='Этап')
    nazvanie = models.CharField('Материал', max_length=255)
    srok_proizvodstva_dney = models.PositiveSmallIntegerField('Срок производства, дней', default=0)
    srok_dostavki_dney = models.PositiveSmallIntegerField('Срок доставки, дней', default=0)
    bufer_dney = models.PositiveSmallIntegerField('Буфер, дней', default=4)
    data_zakaza_fakt = models.DateField('Дата заказа (факт)', null=True, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_NE_ZAKAZAN)

    class Meta:
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['etap__poryadok', 'nazvanie']

    def __str__(self):
        return self.nazvanie

    @cached_property
    def data_zakaza_kraynyaya(self):
        """Крайняя дата заказа = дата НАЧАЛА этапа − производство − доставка − буфер.
        Требование ТЗ (Addendum №2, раздел 16): всегда от даты начала, не окончания."""
        if not self.etap_id:
            return None
        return self.etap.plan_data_nachala - timedelta(
            days=self.srok_proizvodstva_dney + self.srok_dostavki_dney + self.bufer_dney
        )

    @cached_property
    def prosrocheno(self) -> bool:
        if self.status in (self.STATUS_ZAKAZAN, self.STATUS_V_PUTI, self.STATUS_NA_OBEKTE):
            return False
        kraynyaya = self.data_zakaza_kraynyaya
        return bool(kraynyaya and timezone.localdate() > kraynyaya)

    @cached_property
    def dney_do_krayney_daty(self):
        """Сколько дней осталось до крайней даты заказа (отрицательное — просрочено)."""
        kraynyaya = self.data_zakaza_kraynyaya
        if not kraynyaya:
            return None
        return (kraynyaya - timezone.localdate()).days

    @cached_property
    def data_postavki_ozhidaemaya(self):
        """Ожидаемая дата поставки на объект = дата заказа + производство + доставка.
        Считается для уже заказанных материалов (заказан / в пути)."""
        if self.data_zakaza_fakt and self.status in (self.STATUS_ZAKAZAN, self.STATUS_V_PUTI):
            return self.data_zakaza_fakt + timedelta(days=self.srok_proizvodstva_dney + self.srok_dostavki_dney)
        return None

    @cached_property
    def postavka_zaderzhana(self) -> bool:
        """Заказанный материал, ожидаемая поставка которого уже просрочена, но он ещё не на объекте."""
        d = self.data_postavki_ozhidaemaya
        return bool(d and timezone.localdate() > d)

    @cached_property
    def srochno_zakazat(self) -> bool:
        """Ещё не заказан, крайняя дата — в ближайшие 7 дней (но ещё не просрочена)."""
        if self.status != self.STATUS_NE_ZAKAZAN or self.prosrocheno:
            return False
        dney = self.dney_do_krayney_daty
        return dney is not None and 0 <= dney <= 7

    @cached_property
    def status_display_effective(self) -> str:
        if self.prosrocheno:
            return 'Просрочен заказ'
        if self.postavka_zaderzhana:
            return 'Поставка задержана'
        return self.get_status_display()

    @cached_property
    def postavka_kategoriya(self):
        """Категория для экрана поставок: prosrochen_zakaz / zaderzhka_postavki /
        zakazat_srochno / ozhidaetsya / ne_zakazan / na_obekte."""
        if self.status == self.STATUS_NA_OBEKTE:
            return 'na_obekte'
        if self.prosrocheno:
            return 'prosrochen_zakaz'
        if self.postavka_zaderzhana:
            return 'zaderzhka_postavki'
        if self.srochno_zakazat:
            return 'zakazat_srochno'
        if self.status in (self.STATUS_ZAKAZAN, self.STATUS_V_PUTI):
            return 'ozhidaetsya'
        return 'ne_zakazan'


class OplataMontajnika(models.Model):
    """Оплата монтажнику за месяц с защитой от переплаты сверх планового объёма."""

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name='oplaty_montajnikov', verbose_name='Объект')
    montajnik_fio = models.CharField('Монтажник (ФИО)', max_length=255)
    rascenka = models.DecimalField('Расценка за ед., ₽', max_digits=10, decimal_places=2, default=0)
    mesyats = models.DateField('Месяц (1-е число)')
    plan_objem_mesyats = models.DecimalField('Плановый объём за месяц', max_digits=10, decimal_places=2, default=0)
    fact_objem_mesyats = models.DecimalField('Фактический объём за месяц', max_digits=10, decimal_places=2, default=0)
    oplacheno_sverh_grafika = models.BooleanField('Оплата сверх графика подтверждена', default=False)
    summa_oplacheno = models.DecimalField('Уже оплачено, ₽', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Оплата монтажнику'
        verbose_name_plural = 'Оплата бригаде'
        ordering = ['-mesyats', 'montajnik_fio']

    def __str__(self):
        return f'{self.montajnik_fio} — {self.mesyats:%m.%Y}'

    @cached_property
    def prevyshenie_grafika(self) -> bool:
        return self.fact_objem_mesyats > self.plan_objem_mesyats

    @cached_property
    def objem_k_oplate(self) -> Decimal:
        """Объём к оплате: факт, но не выше планового — если не подтверждена оплата сверх графика."""
        if self.oplacheno_sverh_grafika:
            return self.fact_objem_mesyats
        return min(self.fact_objem_mesyats, self.plan_objem_mesyats)

    @cached_property
    def summa_k_oplate(self) -> Decimal:
        return money(self.objem_k_oplate * self.rascenka)

    @cached_property
    def ostatok_k_vyplate(self) -> Decimal:
        return money(self.summa_k_oplate - self.summa_oplacheno)


class RashodMesyachny(models.Model):
    """Месячные расходы объекта."""

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name='rashody', verbose_name='Объект')
    mesyats = models.DateField('Месяц (1-е число)')
    sutochnye = models.DecimalField('Суточные, ₽', max_digits=10, decimal_places=2, default=0)
    arenda_kvartiry = models.DecimalField('Аренда жилья, ₽', max_digits=10, decimal_places=2, default=0)
    oplata_mastera = models.DecimalField('Оплата мастера, ₽', max_digits=10, decimal_places=2, default=0)
    dolya_ofisa = models.DecimalField('Доля офисных расходов, ₽', max_digits=10, decimal_places=2, default=0)
    prochee = models.DecimalField('Прочее, ₽', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Месячный расход'
        verbose_name_plural = 'Расходы объекта'
        ordering = ['-mesyats']

    def __str__(self):
        return f'Расходы {self.mesyats:%m.%Y}'

    @cached_property
    def itogo(self) -> Decimal:
        return money(self.sutochnye + self.arenda_kvartiry + self.oplata_mastera + self.dolya_ofisa + self.prochee)


class DvizhenieDeneg(models.Model):
    """Приход денег от заказчика по этапам с учётом гарантийного удержания."""

    STATUS_OZHIDAETSYA = 'ozhidaetsya'
    STATUS_POLUCHENO = 'polucheno'
    STATUS_PROSROCHENO = 'prosrocheno'
    STATUS_CHOICES = [
        (STATUS_OZHIDAETSYA, 'Ожидается'),
        (STATUS_POLUCHENO, 'Получено'),
        (STATUS_PROSROCHENO, 'Просрочено'),
    ]

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name='dvizhenie_deneg', verbose_name='Объект')
    etap = models.ForeignKey(EtapGrafika, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    osnovanie = models.CharField('Основание', max_length=255, help_text='«Аванс» / «Акт за этап X»')
    summa_nachislenie = models.DecimalField('Сумма начисления, ₽', max_digits=12, decimal_places=2, default=0)
    data_plan = models.DateField('Плановая дата')
    data_fakt = models.DateField('Фактическая дата', null=True, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OZHIDAETSYA)

    class Meta:
        verbose_name = 'Движение денег'
        verbose_name_plural = 'Деньги от заказчика'
        ordering = ['data_plan', 'id']

    def __str__(self):
        return f'{self.osnovanie} — {self.summa_nachislenie} ₽'

    @cached_property
    def summa_za_vychetom_garantii(self) -> Decimal:
        procent = self.objekt.garantiynoe_uderzhanie_procent
        return money(self.summa_nachislenie * (100 - procent) / 100)


class AiZapros(models.Model):
    """Лог обращений к AI-ассистенту прораба — для учёта лимита по тарифу и истории чата."""

    objekt = models.ForeignKey(Objekt, on_delete=models.CASCADE, related_name='ai_zaprosy', verbose_name='Объект')
    vopros = models.TextField('Вопрос')
    otvet = models.TextField('Ответ')
    demo_rezhim = models.BooleanField('Демо-режим (без ключа Anthropic)', default=False)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Запрос к AI-ассистенту'
        verbose_name_plural = 'Запросы к AI-ассистенту'
        ordering = ['data']

    def __str__(self):
        return f'{self.objekt.nazvanie}: {self.vopros[:50]}'
