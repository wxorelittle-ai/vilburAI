# -*- coding: utf-8 -*-
"""Тесты тарификации: лимиты по тарифу, счётчики LimitTracker, истечение подписки
и безопасность вебхука ЮKassa (нельзя активировать тариф поддельным уведомлением)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Brigada
from billing.limits import check_limit
from billing.models import LimitTracker, Platezh
from documents.models import Dokument
from calculator.models import Raschet

TRUSTED_IP = '185.71.76.1'      # из официальной сети ЮKassa 185.71.76.0/27
KEYS = dict(YOOKASSA_SHOP_ID='shop', YOOKASSA_SECRET_KEY='secret')


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


class WebhookBezopasnostTests(TestCase):
    """Поддельное уведомление не должно активировать платный тариф."""

    def setUp(self):
        self.b = brig(tarif='start', uniq='wh')
        self.p = Platezh.objects.create(brigada=self.b, summa=Decimal('990'), tarif='brigadir',
                                        yookassa_id='2d8f1c00-0000-5000-9000-1a2b3c4d5e6f')
        self.telo = {'event': 'payment.succeeded', 'object': {'id': self.p.yookassa_id}}

    def _post(self, ip=TRUSTED_IP):
        return self.client.post('/billing/webhook/', data=self.telo,
                                content_type='application/json', HTTP_X_REAL_IP=ip)

    def _tarif(self):
        self.b.refresh_from_db()
        return self.b.tarif

    def test_v_demo_rezhime_webhook_otklonyon(self):
        """Без ключей ЮKassa настоящих уведомлений не бывает — значит это подделка."""
        r = self._post()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._tarif(), 'start')

    @override_settings(**KEYS)
    def test_chuzhoy_ip_otklonyon(self):
        r = self._post(ip='203.0.113.7')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._tarif(), 'start')

    @override_settings(**KEYS)
    @mock.patch('billing.yookassa_client.podtverdit_platezh')
    def test_nepodtverzhdyonny_platezh_otklonyon(self, api):
        """Главная защита: ЮKassa says «не оплачен» → тариф не активируется."""
        api.return_value = {'status': 'pending', 'paid': False,
                            'summa': Decimal('990'), 'valyuta': 'RUB'}
        r = self._post()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._tarif(), 'start')

    @override_settings(**KEYS)
    @mock.patch('billing.yookassa_client.podtverdit_platezh')
    def test_nesovpadenie_summy_otklonyono(self, api):
        api.return_value = {'status': 'succeeded', 'paid': True,
                            'summa': Decimal('1'), 'valyuta': 'RUB'}   # заплатил 1 ₽ вместо 990
        r = self._post()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self._tarif(), 'start')

    @override_settings(**KEYS)
    @mock.patch('billing.yookassa_client.podtverdit_platezh')
    def test_podtverzhdyonny_platezh_aktiviruet_tarif(self, api):
        api.return_value = {'status': 'succeeded', 'paid': True,
                            'summa': Decimal('990'), 'valyuta': 'RUB'}
        r = self._post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._tarif(), 'brigadir')
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, Platezh.STATUS_OPLACHEN)


class SignalTests(TestCase):
    def test_schetchiki_rastut_pri_sozdanii(self):
        b = brig(tarif='pro')
        Dokument.objects.create(brigada=b, tip='dogovor', zakazchik='И', adres_obekta='А', summa=1)
        Raschet.objects.create(brigada=b, ploshad=10)
        t = LimitTracker.get_or_create_current(b)
        self.assertEqual(t.dokumenty_ispolzovano, 1)
        self.assertEqual(t.raschety_ispolzovano, 1)
