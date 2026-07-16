# -*- coding: utf-8 -*-
"""Тесты маркетплейса: каталог считает репутацию пакетно (без N+1) и пакетные
функции дают тот же результат, что и поштучные."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Brigada
from documents.models import Dokument
from marketplace import reputation
from marketplace.models import Otzyv


def brigada(n, tarif='pro'):
    u = get_user_model().objects.create_user(f'm{n}', password='x')
    return Brigada.objects.create(user=u, nazvanie=f'Бригада {n}', telefon='+79990000000',
                                  region='Тюмень', tarif=tarif,
                                  data_okonchaniya_tarifa=date.today() + timedelta(days=30))


def dokument(b):
    return Dokument.objects.create(brigada=b, tip='dogovor', zakazchik='З',
                                   adres_obekta='А', summa=1000)


class ReputaciyaTests(TestCase):
    def test_paketnye_sovpadayut_s_poshtuchnymi(self):
        """Пакетные версии должны давать тот же ответ, что и на одну бригаду."""
        b1, b2 = brigada(1), brigada(2)
        for _ in range(3):
            dokument(b1)              # 3 документа → подтверждена
        dokument(b2)                  # 1 документ → нет
        Otzyv.objects.create(brigada=b1, avtor_imya='А', ocenka=5, tekst='т', opublikovan=True)

        ids = [b1.pk, b2.pk]
        self.assertEqual(reputation.reytingi(ids)[b1.pk], reputation.reyting(b1))
        podtv = reputation.podtverzhdennye(ids)
        self.assertEqual(b1.pk in podtv, reputation.podtverzhdena(b1))
        self.assertEqual(b2.pk in podtv, reputation.podtverzhdena(b2))
        self.assertTrue(b1.pk in podtv)
        self.assertFalse(b2.pk in podtv)


class KatalogTests(TestCase):
    def test_katalog_ne_rastyot_po_zaprosam(self):
        """Каталог считает репутацию пакетно: число запросов не зависит от числа бригад.
        Сравниваем не абсолютное значение, а рост — так тест не ломается от изменений
        вокруг (сессия, авто-вход) и ловит именно возврат N+1."""
        url = reverse('marketplace:katalog')

        def napolnit(ot, do):
            for i in range(ot, do):
                b = brigada(i)
                dokument(b)
                Otzyv.objects.create(brigada=b, avtor_imya='А', ocenka=4, tekst='т', opublikovan=True)

        napolnit(0, 3)
        self.client.get(url)                       # прогрев: авто-вход создаёт владельца и сессию

        with CaptureQueriesContext(connection) as c1:
            self.assertEqual(self.client.get(url).status_code, 200)

        napolnit(3, 12)                            # бригад втрое больше
        with CaptureQueriesContext(connection) as c2:
            self.assertEqual(self.client.get(url).status_code, 200)

        self.assertEqual(len(c1.captured_queries), len(c2.captured_queries),
                         'число запросов выросло с числом бригад — вернулся N+1')

    def test_pokazyvayutsya_tolko_zhivye_profili(self):
        pustaya = brigada(50)          # без документов и отзывов
        zhivaya = brigada(51)
        dokument(zhivaya)
        r = self.client.get(reverse('marketplace:katalog'))
        self.assertContains(r, zhivaya.nazvanie)
        self.assertNotContains(r, pustaya.nazvanie)
