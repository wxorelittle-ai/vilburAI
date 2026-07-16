import secrets
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils.functional import cached_property


def money(value) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def smeta_pdf_path(instance, filename):
    return f'smety/{instance.brigada_id}/{filename}'


class BazaCen(models.Model):
    """
    База типовых работ (раздел 4.4 / Модуль B ТЗ): 50+ позиций с ценами по трём
    уровням. Наполняется сид-данными при миграции (см. migrations/0002_seed_bazacen.py)
    и далее управляется через админку (раздел «Требования к результату» ТЗ).
    Цены — ориентировочные средние по РФ; для конкретного региона бригада правит
    их в админке под свой рынок.
    """

    KATEGORIYA_CHOICES = [
        ('demontazh', 'Демонтаж'),
        ('steny', 'Стены'),
        ('poly', 'Полы'),
        ('potolki', 'Потолки'),
        ('plitka', 'Плитка'),
        ('elektrika', 'Электрика'),
        ('santehnika', 'Сантехника'),
        ('okna_dveri', 'Окна и двери'),
        ('pokraska', 'Покраска и отделка'),
        ('prochee', 'Прочее'),
    ]

    nazvanie = models.CharField('Наименование работы', max_length=255)
    edinica = models.CharField('Ед. изм.', max_length=20, default='м²')
    kategoriya = models.CharField('Категория', max_length=20, choices=KATEGORIYA_CHOICES, default='prochee')
    region = models.CharField('Регион', max_length=100, blank=True, help_text='Пусто — цена применяется по всем регионам')

    cena_econom = models.DecimalField('Цена, эконом ₽', max_digits=10, decimal_places=2, default=0)
    cena_srednyaya = models.DecimalField('Цена, средняя ₽', max_digits=10, decimal_places=2, default=0)
    cena_premium = models.DecimalField('Цена, премиум ₽', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Позиция базы цен'
        verbose_name_plural = 'База цен'
        ordering = ['kategoriya', 'nazvanie']

    def __str__(self):
        return f'{self.nazvanie} ({self.edinica})'

    def cena_dlya_urovnya(self, uroven: str) -> Decimal:
        return {
            'econom': self.cena_econom,
            'srednyaya': self.cena_srednyaya,
            'premium': self.cena_premium,
        }.get(uroven, self.cena_srednyaya)


class Smeta(models.Model):
    """Смета (раздел 4.4 / Модуль B ТЗ)."""

    UROVEN_CHOICES = [
        ('econom', 'Эконом'),
        ('srednyaya', 'Средний'),
        ('premium', 'Премиум'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('public', 'Опубликована'),
    ]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='smety', verbose_name='Бригада')
    nomer = models.CharField('Номер сметы', max_length=30, blank=True)
    nazvanie = models.CharField('Название сметы', max_length=255)
    adres = models.CharField('Адрес объекта', max_length=500, blank=True)
    zakazchik = models.CharField('Заказчик', max_length=255, blank=True)
    urovne_cen = models.CharField('Уровень цен', max_length=10, choices=UROVEN_CHOICES, default='srednyaya')
    srok_dney = models.PositiveSmallIntegerField('Срок выполнения, дней', null=True, blank=True)

    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='draft')
    public_slug = models.SlugField('Публичная ссылка', max_length=16, unique=True, blank=True, null=True)

    pdf_file = models.FileField('PDF-файл', upload_to=smeta_pdf_path, blank=True, null=True)
    data = models.DateTimeField('Дата создания', auto_now_add=True)
    data_izmeneniya = models.DateTimeField('Дата изменения', auto_now=True)

    class Meta:
        verbose_name = 'Смета'
        verbose_name_plural = 'Сметы'
        ordering = ['-data']
        indexes = [models.Index(fields=['brigada', '-data'])]

    def __str__(self):
        return f'Смета №{self.nomer or self.pk} — {self.nazvanie}'

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.nomer:
            self.nomer = f'СМ-{self.pk:05d}'
            Smeta.objects.filter(pk=self.pk).update(nomer=self.nomer)

    def ensure_public_slug(self):
        if not self.public_slug:
            self.public_slug = secrets.token_urlsafe(6).replace('_', '').replace('-', '')[:10]
            self.save(update_fields=['public_slug'])

    @cached_property
    def itogo(self) -> Decimal:
        return money(sum((r.summa for r in self.raboty.all()), Decimal('0.00')))

    @property
    def is_public(self):
        return self.status == 'public' and bool(self.public_slug)


class SmetaRabota(models.Model):
    """Позиция (строка работ) сметы с автоподсчётом суммы (раздел 4.4 ТЗ)."""

    smeta = models.ForeignKey(Smeta, on_delete=models.CASCADE, related_name='raboty')
    baza_cen = models.ForeignKey(BazaCen, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    nazvanie = models.CharField('Наименование работы', max_length=255)
    edinica = models.CharField('Ед. изм.', max_length=20, default='м²')
    kolvo = models.DecimalField('Кол-во', max_digits=10, decimal_places=2, default=0)
    cena = models.DecimalField('Цена за ед., ₽', max_digits=10, decimal_places=2, default=0)
    poryadok = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Позиция сметы'
        verbose_name_plural = 'Позиции сметы'
        ordering = ['poryadok', 'id']

    def __str__(self):
        return self.nazvanie

    @property
    def summa(self) -> Decimal:
        return money(self.kolvo * self.cena)
