"""Модуль G — Фото-акты (Addendum №1 ТЗ, разделы 4.7 / «Модуль G»)."""

from django.db import models


def fotoakt_path(instance, filename):
    return f'fotoakty/{instance.dokument.brigada_id}/{instance.dokument_id}/{filename}'


class FotoAkt(models.Model):
    """Фотография, привязанная к акту приёмки этапа. Хранит геометку и текст водяного знака."""

    dokument = models.ForeignKey('documents.Dokument', on_delete=models.CASCADE, related_name='fotoakty', verbose_name='Документ')
    foto_file = models.ImageField('Фото', upload_to=fotoakt_path)
    watermark_text = models.CharField('Водяной знак', max_length=255, blank=True)
    geo_lat = models.FloatField('Широта', null=True, blank=True)
    geo_lon = models.FloatField('Долгота', null=True, blank=True)
    podpis_snizu = models.CharField('Подпись под фото', max_length=255, blank=True)
    data_zagruzki = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        verbose_name = 'Фото акта'
        verbose_name_plural = 'Фото-акты'
        ordering = ['data_zagruzki']

    def __str__(self):
        return f'Фото {self.dokument.nomer}'

    @property
    def est_geo(self) -> bool:
        return self.geo_lat is not None and self.geo_lon is not None

    @property
    def geo_ssylka(self):
        if self.est_geo:
            return f'https://yandex.ru/maps/?pt={self.geo_lon},{self.geo_lat}&z=17&l=map'
        return None
