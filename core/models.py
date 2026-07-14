from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


phone_validator = RegexValidator(
    regex=r'^\+?7\d{10}$',
    message='Телефон в формате +79991234567',
)


class Brigada(models.Model):
    """
    Профиль бригады — расширение стандартного User Django (раздел 4.1 ТЗ).
    Каждый зарегистрированный пользователь сервиса — это бригада (или ИП/самозанятый мастер).
    """

    TARIF_CHOICES = [
        ('start', 'Старт'),
        ('samozanyaty', 'Самозанятый'),
        ('brigadir', 'Бригадир'),
        ('pro', 'PRO'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='brigada',
        verbose_name='Пользователь',
    )
    nazvanie = models.CharField('Название бригады', max_length=255)
    telefon = models.CharField('Телефон', max_length=20, validators=[phone_validator])
    rekvizity = models.TextField('Реквизиты (ИНН, счёт и т.д.)', blank=True)
    logo = models.ImageField('Логотип', upload_to='logos/', blank=True, null=True)
    region = models.CharField('Регион', max_length=100, blank=True)

    tarif = models.CharField('Тариф', max_length=20, choices=TARIF_CHOICES, default='start')
    data_okonchaniya_tarifa = models.DateField('Дата окончания тарифа', null=True, blank=True)

    data_registracii = models.DateTimeField('Дата регистрации', auto_now_add=True)

    class Meta:
        verbose_name = 'Бригада'
        verbose_name_plural = 'Бригады'
        ordering = ['-data_registracii']

    def __str__(self):
        return self.nazvanie

    @property
    def tarif_aktiven(self):
        """Проверка, действует ли платный тариф (не истёк ли период)."""
        if self.tarif == 'start':
            return True
        if not self.data_okonchaniya_tarifa:
            return False
        return self.data_okonchaniya_tarifa >= timezone.localdate()

    @property
    def effective_tarif(self):
        """
        Тариф, который реально действует прямо сейчас: если оплаченный период истёк,
        бригада фактически на «Старте», хотя поле tarif ещё хранит прежнее значение
        (раздел 5 ТЗ: «переход на Старт с сохранением истории»).
        """
        return self.tarif if self.tarif_aktiven else 'start'

    @property
    def tarif_label(self):
        return dict(self.TARIF_CHOICES).get(self.tarif, self.tarif)
