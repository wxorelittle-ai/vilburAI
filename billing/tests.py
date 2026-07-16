# -*- coding: utf-8 -*-
"""Тесты тарификации: лимиты по тарифу, счётчики LimitTracker, истечение подписки."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Brigada
from billing.limits import check_limit
from billing.models import LimitTracker
from documents.models import Dokument
from calculator.models import Raschet


def brig(tarif='start', dney=30, uniq='b'):
    u = get_user_model().objects.create_user(f'{uniq}{get_user_model().objects.count()}', password='x')
    return Brigada.objects.create(
        user=u, nazvanie='Т', telefon='+79990000000', tarif=tarif,
        data_okonchaniya_tarifa=(date.today() + timedelta(days=dney)) if dney is not None else None)


class TarifTests(TestCase):
    def test_effective_tarif_pri_istechenii(self):
        """Истёк оплаченный период → фактически «Старт» (история сохраняется)."""
        b = brig(tarif='pro', dney=-1)
        self.assertFalse(b.tarif_aktiven)
        self.assertEqual(b.effective_tarif, 'start')
        self.assertEqual(b.tarif, 'pro')          # поле не затирается

    def test_start_vsegda_aktiven(self):
        b = brig(tarif='start', dney=None)
        self.assertTrue(b.tarif_aktiven)
        self.assertEqual(b.effective_tarif, 'start')


class LimitTests(TestCase):
    def test_start_limit_dokumentov(self):
        b = brig(tarif='start')
        lc = check_limit(b, 'dokumenty')
        self.assertEqual(lc.limit, 1)
        self.assertFalse(lc.exceeded)
        LimitTracker.increment(b, 'dokumenty_ispolzovano')
        self.assertTrue(check_limit(b, 'dokumenty').exceeded)   # 1 из 1 — исчерпан

    def test_bezlimit(self):
        b = brig(tarif='pro')
        lc = check_limit(b, 'dokumenty')
        self.assertIsNone(lc.limit)
        self.assertTrue(lc.unlimited)
        self.assertFalse(lc.exceeded)

    def test_limit_po_effective_tarifu(self):
        """Лимиты считаются по действующему тарифу, а не по полю tarif."""
        b = brig(tarif='pro', dney=-1)          # подписка истекла
        self.assertEqual(check_limit(b, 'dokumenty').limit, 1)   # как на «Старте»


class SignalTests(TestCase):
    def test_schetchiki_rastut_pri_sozdanii(self):
        b = brig(tarif='pro')
        Dokument.objects.create(brigada=b, tip='dogovor', zakazchik='И', adres_obekta='А', summa=1)
        Raschet.objects.create(brigada=b, ploshad=10)
        t = LimitTracker.get_or_create_current(b)
        self.assertEqual(t.dokumenty_ispolzovano, 1)
        self.assertEqual(t.raschety_ispolzovano, 1)
