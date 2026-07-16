# -*- coding: utf-8 -*-
"""Тесты смет (Модуль B) и безопасности публичной ссылки.

Раздел 8 ТЗ: публичная смета доступна без авторизации, только на чтение,
чувствительные данные бригады (телефон, реквизиты) скрыты.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from core.models import Brigada
from smety.models import Smeta, SmetaRabota, BazaCen

TELEFON = '+79995554433'
REKVIZITY = 'ИНН 720312345678, р/с 40802810067100012345'


def brigada(uniq='s'):
    u = get_user_model().objects.create_user(f'{uniq}{get_user_model().objects.count()}', password='x')
    return Brigada.objects.create(user=u, nazvanie='Бригада СибСтрой', telefon=TELEFON,
                                  rekvizity=REKVIZITY, tarif='pro',
                                  data_okonchaniya_tarifa=timezone.localdate() + timedelta(days=30))


def smeta_s_rabotami(b=None, publish=True):
    b = b or brigada()
    s = Smeta.objects.create(brigada=b, nazvanie='Ремонт кухни', adres='Тюмень, Мельникайте 137',
                             zakazchik='Иванов', srok_dney=20)
    SmetaRabota.objects.create(smeta=s, nazvanie='Штукатурка', edinica='м²', kolvo=10, cena=500)
    SmetaRabota.objects.create(smeta=s, nazvanie='Плитка', edinica='м²', kolvo=5, cena=1200)
    if publish:
        s.status = 'public'
        s.save(update_fields=['status'])   # ensure_public_slug() пишет только слаг
        s.ensure_public_slug()
    return s


class SmetaModelTests(TestCase):
    def test_itogo_summiruet_pozicii(self):
        s = smeta_s_rabotami(publish=False)
        self.assertEqual(s.itogo, Decimal('11000.00'))    # 10*500 + 5*1200

    def test_nomer_generiruetsya(self):
        s = smeta_s_rabotami(publish=False)
        self.assertTrue(s.nomer.startswith('СМ-'))

    def test_publichnaya_ssylka_unikalna(self):
        s1, s2 = smeta_s_rabotami(), smeta_s_rabotami()
        self.assertNotEqual(s1.public_slug, s2.public_slug)
        self.assertTrue(s1.is_public)

    def test_chernovik_ne_publichny(self):
        s = smeta_s_rabotami(publish=False)
        self.assertFalse(s.is_public)

    def test_cena_po_urovnyu(self):
        b = BazaCen.objects.create(nazvanie='Работа', cena_econom=100, cena_srednyaya=200, cena_premium=300)
        self.assertEqual(b.cena_dlya_urovnya('econom'), 100)
        self.assertEqual(b.cena_dlya_urovnya('premium'), 300)
        self.assertEqual(b.cena_dlya_urovnya('неизвестный'), 200)   # по умолчанию средний


@override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
class PublichnayaSmetaTests(TestCase):
    """Ссылку на смету владелец отправляет заказчику — она не должна открывать кабинет."""

    def setUp(self):
        self.s = smeta_s_rabotami()
        self.url = reverse('public_smeta', args=[self.s.public_slug])

    def test_dostupna_bez_avtorizacii(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Ремонт кухни')
        self.assertContains(r, 'Штукатурка')

    def test_ne_svetit_telefon_i_rekvizity(self):
        """Раздел 8 ТЗ: заказчик видит только название бригады."""
        r = self.client.get(self.url)
        self.assertContains(r, 'Бригада СибСтрой')
        self.assertNotContains(r, TELEFON)
        self.assertNotContains(r, 'ИНН 720312345678')
        self.assertNotContains(r, '40802810067100012345')

    def test_ssylka_ne_avtologinit_zakazchika(self):
        """Публичная смета исключена из авто-входа: открывший ссылку остаётся анонимом
        и не получает сессию владельца.

        ВНИМАНИЕ: это не защищает кабинет целиком — при AUTO_LOGIN=True любой, кто
        откроет корень сайта, войдёт владельцем. Полная защита — AUTO_LOGIN=False.
        """
        r = self.client.get(self.url)
        self.assertFalse(r.wsgi_request.user.is_authenticated,
                         'ссылка на смету выдала заказчику сессию владельца')

    def test_na_stranice_net_menyu_vladelca(self):
        r = self.client.get(self.url)
        self.assertNotContains(r, 'Выйти')
        self.assertNotContains(r, 'Профиль')

    def test_chernovik_ne_otkryvaetsya(self):
        s = smeta_s_rabotami(publish=False)
        s.public_slug = 'draftslug'
        s.save(update_fields=['public_slug'])
        r = self.client.get(reverse('public_smeta', args=['draftslug']))
        self.assertEqual(r.status_code, 404)

    def test_net_ssylki_na_skachivanie(self):
        """ТЗ: публичная смета — просмотр без скачивания."""
        r = self.client.get(self.url)
        self.assertNotContains(r, 'Скачать')
