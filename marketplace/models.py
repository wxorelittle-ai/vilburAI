"""
Модуль 4 — Маркетплейс (раздел 3 ТЗ):
- Otzyv — репутационная система бригад (отзывы, оценка, подтверждённый статус);
- IzlishekMateriala — биржа излишков материалов между бригадами;
- Tender + TenderOtklik — тендерная площадка (заявка → отклики с ценой).
"""

from django.db import models
from django.utils import timezone


class Otzyv(models.Model):
    """Отзыв о бригаде (оставляют заказчики). Формирует репутацию в каталоге."""

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='otzyvy', verbose_name='Бригада')
    avtor_imya = models.CharField('Имя автора', max_length=120)
    ocenka = models.PositiveSmallIntegerField('Оценка (1–5)', default=5)
    tekst = models.TextField('Отзыв')
    obekt = models.CharField('Объект / город', max_length=200, blank=True)
    podtverzhden = models.BooleanField('Подтверждён (сделка через сервис)', default=False)
    opublikovan = models.BooleanField('Опубликован', default=True)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-data']

    def __str__(self):
        return f'{self.brigada.nazvanie} — {self.ocenka}/5 от {self.avtor_imya}'


class IzlishekMateriala(models.Model):
    """Объявление о продаже излишков материалов (биржа между бригадами)."""

    STATUS_AKTIVNO = 'aktivno'
    STATUS_PRODANO = 'prodano'
    STATUS_CHOICES = [(STATUS_AKTIVNO, 'Активно'), (STATUS_PRODANO, 'Продано / снято')]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='izlishki', verbose_name='Бригада')
    nazvanie = models.CharField('Материал', max_length=200)
    kolvo = models.DecimalField('Количество', max_digits=10, decimal_places=2, default=0)
    edinica = models.CharField('Ед. изм.', max_length=20, default='шт')
    cena = models.DecimalField('Цена за ед., ₽', max_digits=10, decimal_places=2, default=0)
    region = models.CharField('Регион / город', max_length=120, blank=True)
    opisanie = models.TextField('Описание', blank=True)
    kontakt_telefon = models.CharField('Телефон для связи', max_length=20)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_AKTIVNO)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Излишек материала'
        verbose_name_plural = 'Биржа излишков'
        ordering = ['-data']

    def __str__(self):
        return f'{self.nazvanie} — {self.kolvo} {self.edinica}'

    @property
    def summa(self):
        return self.kolvo * self.cena


class Tender(models.Model):
    """Тендер: заказчик/прораб публикует заявку, бригады откликаются ценой."""

    STATUS_OTKRYT = 'otkryt'
    STATUS_ZAKRYT = 'zakryt'
    STATUS_CHOICES = [(STATUS_OTKRYT, 'Открыт'), (STATUS_ZAKRYT, 'Закрыт')]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='tendery', verbose_name='Автор')
    nazvanie = models.CharField('Название заявки', max_length=200)
    opisanie = models.TextField('Что нужно сделать')
    region = models.CharField('Регион / адрес', max_length=200, blank=True)
    byudzhet = models.DecimalField('Ориентировочный бюджет, ₽', max_digits=12, decimal_places=2, null=True, blank=True)
    srok_do = models.DateField('Отклики до', null=True, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OTKRYT)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Тендер'
        verbose_name_plural = 'Тендеры'
        ordering = ['-data']

    def __str__(self):
        return self.nazvanie

    @property
    def otkryt(self) -> bool:
        if self.status != self.STATUS_OTKRYT:
            return False
        if self.srok_do and self.srok_do < timezone.localdate():
            return False
        return True

    @property
    def otklikov(self) -> int:
        return self.otkliki.count()


class TenderOtklik(models.Model):
    """Отклик бригады на тендер с предложенной ценой."""

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='otkliki', verbose_name='Тендер')
    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='otkliki', verbose_name='Бригада')
    cena = models.DecimalField('Предложенная цена, ₽', max_digits=12, decimal_places=2)
    srok_dney = models.PositiveSmallIntegerField('Срок, дней', null=True, blank=True)
    kommentariy = models.TextField('Комментарий', blank=True)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Отклик на тендер'
        verbose_name_plural = 'Отклики на тендеры'
        ordering = ['cena']
        unique_together = [('tender', 'brigada')]

    def __str__(self):
        return f'{self.brigada.nazvanie} → {self.cena} ₽'
