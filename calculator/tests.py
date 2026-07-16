# -*- coding: utf-8 -*-
"""Тесты калькулятора себестоимости (Модуль C) — денежные формулы."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Brigada
from calculator.models import Raschet


def brig():
    u = get_user_model().objects.create_user('calc_user', password='x')
    return Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif='pro',
                                  data_okonchaniya_tarifa=date.today() + timedelta(days=30))


class RaschetTests(TestCase):
    def setUp(self):
        self.r = Raschet.objects.create(
            brigada=brig(), ploshad=Decimal('10'), kolvo_rabochih=1, dni=1,
            stavka_v_den=Decimal('1000'), arenda=0, dostavka=0, rashodniki=0, nalog='0')

    def test_sebestoimost(self):
        self.assertEqual(self.r.trudozatraty, Decimal('1000.00'))
        self.assertEqual(self.r.sebestoimost_obshaya, Decimal('1000.00'))
        self.assertEqual(self.r.sebestoimost_m2, Decimal('100.00'))

    def test_postoyannye_raskhody(self):
        self.r.arenda = Decimal('100'); self.r.dostavka = Decimal('200'); self.r.rashodniki = Decimal('300')
        self.assertEqual(self.r.postoyannye_raskhody, Decimal('600.00'))
        self.assertEqual(self.r.sebestoimost_obshaya, Decimal('1600.00'))

    def test_cena_bez_naloga(self):
        self.assertEqual(self.r.cena_30, Decimal('1300.00'))
        self.assertEqual(self.r.cena_50, Decimal('1500.00'))

    def test_cena_s_nalogom(self):
        """Цена делится на (1 − ставка), чтобы после налога осталась заложенная прибыль."""
        self.r.nalog = '4'
        self.assertEqual(self.r.cena_30, Decimal('1354.17'))  # 1000*1.3/0.96

    def test_sebestoimost_m2_pri_nulevoy_ploshadi(self):
        self.r.ploshad = Decimal('0')
        self.assertEqual(self.r.sebestoimost_m2, Decimal('0.00'))
        self.assertEqual(self.r.cena_30_m2, Decimal('0.00'))
