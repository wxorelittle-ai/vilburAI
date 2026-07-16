# -*- coding: utf-8 -*-
"""Тесты ядра: авто-вход владельца (однопользовательский режим) и отсутствие лендинга."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from core.models import Brigada


@override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
class AutoLoginTests(TestCase):
    def test_koren_vedyot_srazu_v_kabinet(self):
        """Лендинга нет: / → /dashboard/ без страницы входа."""
        r = self.client.get('/', follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.request['PATH_INFO'], reverse('core:dashboard'))

    def test_vladelec_sozdayotsya_avtomaticheski(self):
        self.client.get('/dashboard/')
        u = get_user_model().objects.get(username='vladelec')
        self.assertTrue(hasattr(u, 'brigada'))
        self.assertEqual(u.brigada.tarif, 'pro')      # все модули открыты

    def test_admin_ne_avtologinitsya(self):
        """Админка исключена из авто-входа и требует обычной авторизации."""
        r = self.client.get('/admin/', follow=True)
        self.assertIn('login', r.request['PATH_INFO'])


@override_settings(AUTO_LOGIN=False)
class BezAutoLoginTests(TestCase):
    def test_dashboard_trebuet_vhoda(self):
        r = self.client.get('/dashboard/', follow=True)
        self.assertIn('login', r.request['PATH_INFO'])


@override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
class AutoLoginBezSessiyTests(TestCase):
    """Авто-вход не должен плодить сессии: сайт открыт, по нему ходят боты и сканеры —
    иначе каждая их страница = строка в django_session (на бою так набежало 2175)."""

    def test_ne_sozdayot_sessii_v_bd(self):
        from django.contrib.sessions.models import Session
        for _ in range(5):
            self.client.cookies.clear()          # каждый раз как новый посетитель
            self.assertEqual(self.client.get('/dashboard/').status_code, 200)
        self.assertEqual(Session.objects.count(), 0)

    def test_polzovatel_vsyo_ravno_avtorizovan(self):
        r = self.client.get('/dashboard/')
        self.assertTrue(r.wsgi_request.user.is_authenticated)
        self.assertEqual(r.wsgi_request.user.username, 'vladelec')


class HealthzTests(TestCase):
    def test_otvechaet_ok(self):
        r = self.client.get('/healthz')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'ok')

    @override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
    def test_ne_sozdayot_polzovatelya_i_sessiyu(self):
        """Пинги мониторинга не должны заводить владельца и сессии."""
        from django.contrib.sessions.models import Session
        self.client.get('/healthz')
        self.assertFalse(get_user_model().objects.filter(username='vladelec').exists())
        self.assertEqual(Session.objects.count(), 0)


@override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
class ShablonyNeTekutTests(TestCase):
    """В отрисованной странице не должно остаться сырого синтаксиса шаблонов.

    Повод: `{# ... #}` в Django — ОДНОСТРОЧНЫЙ. Многострочный комментарий не
    распознаётся и выводится на страницу видимым текстом; в шапке он вдобавок стал
    элементом флекса и ломал вёрстку (страница 426px при экране 375).
    Для многострочных — только {% comment %}.
    """

    STRANICY = ['/dashboard/', '/documents/', '/smety/', '/objekty/', '/billing/',
                '/nalogi/', '/proverka/', '/market/', '/profile/']

    def test_net_syrogo_sintaksisa_shablonov(self):
        # Только {# и {% : `}}` и `{{` дают ложные срабатывания на инлайновом JS
        # (например, `catch(e){}})();` в шапке).
        for url in self.STRANICY:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                for marker in ('{#', '{%'):
                    self.assertNotIn(marker, html,
                                     f'на {url} в HTML протёк шаблонный тег {marker}')


class BrigadaTests(TestCase):
    def test_tarif_label(self):
        u = get_user_model().objects.create_user('bt', password='x')
        b = Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif='brigadir')
        self.assertEqual(b.tarif_label, 'Бригадир')
        self.assertEqual(str(b), 'Т')


class DashboardDelaTests(TestCase):
    """Лента «что горит» собирается из настоящих дедлайнов, а не из выдуманных задач."""

    def setUp(self):
        from datetime import date, timedelta
        from decimal import Decimal
        from objekty.models import Objekt, EtapGrafika, Material, DvizhenieDeneg
        self.T = timezone.localdate()
        u = get_user_model().objects.create_user('dash', password='x')
        self.b = Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif='pro',
                                        data_okonchaniya_tarifa=self.T + timedelta(days=30))
        self.ob = Objekt.objects.create(brigada=self.b, nazvanie='Объект', data_nachala=self.T,
                                        data_okonchania_plan=self.T + timedelta(days=30),
                                        summa_dogovora=Decimal('500000'))
        # этап стартует через 3 дня; материал к нему просрочен (крайняя = старт-19)
        e = EtapGrafika.objects.create(objekt=self.ob, nazvanie='Плитка', plan_objem=10,
                                       plan_data_nachala=self.T + timedelta(days=3),
                                       plan_data_okonchania=self.T + timedelta(days=9))
        Material.objects.create(objekt=self.ob, etap=e, nazvanie='Керамогранит',
                                srok_proizvodstva_dney=10, srok_dostavki_dney=5, bufer_dney=4,
                                status=Material.STATUS_NE_ZAKAZAN)
        # просроченный платёж от заказчика
        DvizhenieDeneg.objects.create(objekt=self.ob, osnovanie='Аванс', summa_nachislenie=Decimal('150000'),
                                      data_plan=self.T - timedelta(days=2),
                                      status=DvizhenieDeneg.STATUS_OZHIDAETSYA)

    def test_lenta_sobiraet_dedlayny(self):
        from core.dashboard import blizhayshie_dela
        dela = blizhayshie_dela(self.b)
        tipy = {d['tip'] for d in dela}
        self.assertIn('Материал', tipy)
        self.assertIn('Этап', tipy)
        self.assertIn('Деньги', tipy)
        # просроченное — красное и идёт первым по своей дате
        prosr = [d for d in dela if d['prosrocheno']]
        self.assertTrue(prosr)
        self.assertTrue(all(d['ton'] == 'red' for d in prosr))

    def test_lenta_otsortirovana_po_date(self):
        from core.dashboard import blizhayshie_dela
        daty = [d['data'] for d in blizhayshie_dela(self.b)]
        self.assertEqual(daty, sorted(daty))

    def test_dalyokie_sobytiya_ne_popadayut(self):
        """Горизонт 14 дней: дела за его пределами в ленту не идут."""
        from datetime import timedelta
        from core.dashboard import blizhayshie_dela
        dela = blizhayshie_dela(self.b, dney=14)
        self.assertTrue(all(d['data'] <= self.T + timedelta(days=14) for d in dela))

    def test_finansy_schitayut_balans(self):
        from decimal import Decimal
        from core.dashboard import finansy
        f = finansy(self.b)
        self.assertEqual(f['ozhidaetsya'], Decimal('150000.00'))   # аванс ещё не получен
        self.assertEqual(f['poluchen'], Decimal('0.00'))

    def test_dashboard_otkryvaetsya_s_dannymi(self):
        self.client.force_login(self.b.user)
        r = self.client.get(reverse('core:dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Что горит')
        self.assertContains(r, 'Керамогранит')
