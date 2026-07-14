"""Модуль H — Голосовой ввод (Addendum №1 ТЗ, разделы 4.7 / «Модуль H»)."""

from django.db import models


class GolosovayaKomanda(models.Model):
    STATUS_OBRABOTAN = 'obrabotan'
    STATUS_OSHIBKA = 'oshibka'
    STATUS_CHOICES = [(STATUS_OBRABOTAN, 'Обработана'), (STATUS_OSHIBKA, 'Ошибка')]

    brigada = models.ForeignKey('core.Brigada', on_delete=models.CASCADE, related_name='golosovye', verbose_name='Бригада')
    audio_file = models.FileField('Аудио', upload_to='golos/', null=True, blank=True)
    tekst_raspoznanny = models.TextField('Распознанный текст', blank=True)
    pozicii_najdeno = models.PositiveIntegerField('Найдено позиций', default=0)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OBRABOTAN)
    data = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Голосовая команда'
        verbose_name_plural = 'Голосовые команды'
        ordering = ['-data']

    def __str__(self):
        return self.tekst_raspoznanny[:50] or 'команда'
