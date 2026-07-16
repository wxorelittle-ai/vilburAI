# -*- coding: utf-8 -*-
"""Тесты ядра: авто-вход владельца (однопользовательский режим) и отсутствие лендинга."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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


class BrigadaTests(TestCase):
    def test_tarif_label(self):
        u = get_user_model().objects.create_user('bt', password='x')
        b = Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif='brigadir')
        self.assertEqual(b.tarif_label, 'Бригадир')
        self.assertEqual(str(b), 'Т')
