# -*- coding: utf-8 -*-
"""Тесты ПЭП (Модуль I). Ключевые требования ТЗ (раздел 8/16):
СМС-код хранится ТОЛЬКО в хешированном виде; код нельзя узнать в обход телефона;
IP подписанта — доказательство, его нельзя брать из подделываемого заголовка."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from core.models import Brigada
from documents.models import Dokument
from podpis import sms
from podpis.views import _pep_dostupna
from podpis.models import PodpisZakazchika

SMS_KEY = dict(SMS_API_KEY='real-key')


def brigada(tarif='brigadir', uniq='p'):
    u = get_user_model().objects.create_user(f'{uniq}{get_user_model().objects.count()}', password='x')
    return Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif=tarif,
                                  data_okonchaniya_tarifa=timezone.localdate() + timedelta(days=30))


def dok(b=None):
    b = b or brigada()
    return Dokument.objects.create(brigada=b, tip='dogovor', zakazchik='Иванов',
                                   adres_obekta='Тюмень', summa=100000)


class PodpisTests(TestCase):
    def setUp(self):
        self.p = PodpisZakazchika.objects.create(dokument=dok())

    def test_token_generiruetsya(self):
        self.assertTrue(self.p.token)
        self.assertGreaterEqual(len(self.p.token), 8)

    def test_kod_hranitsya_tolko_heshem(self):
        kod = PodpisZakazchika.sgenerirovat_kod()
        self.p.zapisat_kod(kod)
        self.p.refresh_from_db()
        self.assertNotIn(kod, self.p.kod_sms_hash)      # открытого кода нет
        self.assertTrue(self.p.proverit_kod(kod))       # но проверка проходит
        self.assertFalse(self.p.proverit_kod('000000'))

    def test_kod_shestiznachny(self):
        kod = PodpisZakazchika.sgenerirovat_kod()
        self.assertEqual(len(kod), 6)
        self.assertTrue(kod.isdigit())

    def test_podpisanie_fiksiruet_fakty(self):
        self.p.zapisat_kod('123456')
        self.p.podpisat(telefon='+79995554433', ip='203.0.113.7')
        self.p.refresh_from_db()
        self.assertTrue(self.p.podpisano)
        self.assertEqual(self.p.telefon, '+79995554433')
        self.assertEqual(self.p.ip_adres, '203.0.113.7')
        self.assertIsNotNone(self.p.data_podpisi)
        self.assertEqual(len(self.p.doc_hash), 64)      # SHA-256
        self.assertEqual(self.p.kod_sms_hash, '')       # хеш кода стёрт после подписи

    def test_doc_hash_stabilen(self):
        h1 = self.p.vychislit_doc_hash()
        h2 = self.p.vychislit_doc_hash()
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


class SmsBezopasnostTests(TestCase):
    """Код подписания не должен становиться известен в обход телефона."""

    def test_bez_klyucha_demo_vozvrashchaet_kod(self):
        status, kod = sms.otpravit_kod('+79990000000', '123456')
        self.assertEqual(status, sms.DEMO)
        self.assertEqual(kod, '123456')

    @override_settings(**SMS_KEY)
    @mock.patch('requests.get', side_effect=Exception('сеть упала'))
    def test_sboy_shlyuza_ne_raskryvaet_kod(self, _):
        """Боевой режим + шлюз недоступен → ошибка, код НЕ возвращается.
        Иначе подписал бы любой, у кого есть ссылка, дождавшись сбоя сети."""
        status, kod = sms.otpravit_kod('+79990000000', '123456')
        self.assertEqual(status, sms.OSHIBKA)
        self.assertIsNone(kod)

    @override_settings(**SMS_KEY)
    @mock.patch('requests.get')
    def test_logicheskaya_oshibka_shlyuza_ne_schitaetsya_otpravkoy(self, get):
        """Шлюз отвечает 200 с ошибкой в теле — это не отправка."""
        get.return_value = mock.Mock(status_code=200, raise_for_status=mock.Mock(),
                                     json=mock.Mock(return_value={'status': 'ERROR', 'status_code': 202}))
        status, kod = sms.otpravit_kod('+79990000000', '123456')
        self.assertEqual(status, sms.OSHIBKA)
        self.assertIsNone(kod)

    @override_settings(**SMS_KEY)
    @mock.patch('requests.get')
    def test_uspeshnaya_otpravka(self, get):
        get.return_value = mock.Mock(status_code=200, raise_for_status=mock.Mock(),
                                     json=mock.Mock(return_value={'status': 'OK'}))
        status, kod = sms.otpravit_kod('+79990000000', '123456')
        self.assertEqual(status, sms.OTPRAVLENO)
        self.assertIsNone(kod)


class SignStranicaTests(TestCase):
    def setUp(self):
        self.p = PodpisZakazchika.objects.create(dokument=dok())
        self.url = reverse('podpis:sign', args=[self.p.token])

    def test_dostupna_bez_avtorizacii(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    @override_settings(**SMS_KEY)
    @mock.patch('requests.get', side_effect=Exception('сеть упала'))
    def test_v_boevom_rezhime_kod_ne_pokazyvaetsya_na_stranice(self, _):
        r = self.client.post(self.url, {'action': 'request_code',
                                        'telefon': '+79995554433', 'soglasie': 'on'})
        self.p.refresh_from_db()
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'код показан ниже')
        self.assertContains(r, 'Не удалось отправить')

    def test_v_demo_kod_pokazyvaetsya(self):
        r = self.client.post(self.url, {'action': 'request_code',
                                        'telefon': '+79995554433', 'soglasie': 'on'})
        self.assertContains(r, 'код показан ниже')

    def test_bez_soglasiya_kod_ne_zaprashivaetsya(self):
        self.client.post(self.url, {'action': 'request_code', 'telefon': '+79995554433'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.kod_sms_hash, '')

    def test_nevernyy_kod_ne_podpisyvaet(self):
        self.p.zapisat_kod('123456')
        self.client.post(self.url, {'action': 'confirm', 'kod': '999999'})
        self.p.refresh_from_db()
        self.assertFalse(self.p.podpisano)

    def test_ip_beryotsya_iz_doverennogo_zagolovka(self):
        """X-Forwarded-For подделывается клиентом — в доказательство подписи
        должен попасть X-Real-IP, который проставляет наш nginx."""
        self.p.telefon = '+79995554433'
        self.p.save(update_fields=['telefon'])
        self.p.zapisat_kod('123456')
        self.client.post(self.url, {'action': 'confirm', 'kod': '123456'},
                         HTTP_X_FORWARDED_FOR='1.2.3.4',      # подделка клиента
                         HTTP_X_REAL_IP='203.0.113.9')        # реальный, от nginx
        self.p.refresh_from_db()
        self.assertTrue(self.p.podpisano)
        self.assertEqual(self.p.ip_adres, '203.0.113.9')


class GejtingTests(TestCase):
    def test_pep_tolko_s_brigadira(self):
        self.assertFalse(_pep_dostupna(brigada(tarif='start')))
        self.assertFalse(_pep_dostupna(brigada(tarif='samozanyaty')))
        self.assertTrue(_pep_dostupna(brigada(tarif='brigadir')))
        self.assertTrue(_pep_dostupna(brigada(tarif='pro')))
