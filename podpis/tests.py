# -*- coding: utf-8 -*-
"""Тесты ПЭП (Модуль I). Ключевое требование ТЗ (раздел 8/16):
СМС-код хранится ТОЛЬКО в хешированном виде, в открытом — никогда."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Brigada
from documents.models import Dokument
from podpis.models import PodpisZakazchika


def dok():
    u = get_user_model().objects.create_user('p_user', password='x')
    b = Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif='brigadir',
                               data_okonchaniya_tarifa=date.today() + timedelta(days=30))
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
