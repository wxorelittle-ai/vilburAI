# -*- coding: utf-8 -*-
"""Тесты Модуля J — контроль объекта. Проверяют жёсткие правила ТЗ (раздел 16):
крайняя дата заказа от НАЧАЛА этапа, защита от переплаты монтажнику, гарантийное
удержание, светофор (красный/жёлтый), гейтинг по тарифу и демо-режим AI."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Brigada
from smety.models import Smeta, SmetaRabota
from objekty import ai_assistant, limits
from objekty.views import _create_etapy_from_smeta
from objekty.models import (
    Objekt, EtapGrafika, Material, OplataMontajnika, RashodMesyachny, DvizhenieDeneg,
)


def make_brigada(tarif='brigadir', **kw):
    u = get_user_model().objects.create_user(f'u{get_user_model().objects.count()}', password='x')
    return Brigada.objects.create(
        user=u, nazvanie='Тест', telefon='+79990000000', tarif=tarif,
        data_okonchaniya_tarifa=timezone.localdate() + timedelta(days=30), **kw)


def make_objekt(brigada, **kw):
    T = timezone.localdate()
    defaults = dict(nazvanie='Об', data_nachala=T - timedelta(days=10),
                    data_okonchania_plan=T + timedelta(days=20), summa_dogovora=Decimal('1000000'),
                    garantiynoe_uderzhanie_procent=5)
    defaults.update(kw)
    return Objekt.objects.create(brigada=brigada, **defaults)


class MaterialTests(TestCase):
    def test_kraynyaya_data_ot_nachala_etapa(self):
        """ТЗ раздел 16: крайняя дата заказа = начало этапа − произв − доставка − буфер."""
        b = make_brigada()
        ob = make_objekt(b)
        T = timezone.localdate()
        e = EtapGrafika.objects.create(objekt=ob, nazvanie='Э', plan_objem=10,
                                       plan_data_nachala=T + timedelta(days=30),
                                       plan_data_okonchania=T + timedelta(days=40))
        m = Material.objects.create(objekt=ob, etap=e, nazvanie='Плитка',
                                    srok_proizvodstva_dney=10, srok_dostavki_dney=5, bufer_dney=4)
        self.assertEqual(m.data_zakaza_kraynyaya, e.plan_data_nachala - timedelta(days=19))

    def test_prosrocheno_tolko_dlya_nezakazannyh(self):
        b = make_brigada(); ob = make_objekt(b); T = timezone.localdate()
        e = EtapGrafika.objects.create(objekt=ob, nazvanie='Э', plan_objem=10,
                                       plan_data_nachala=T + timedelta(days=1),
                                       plan_data_okonchania=T + timedelta(days=5))
        # крайняя дата в прошлом (1 - 30 = -29)
        m = Material.objects.create(objekt=ob, etap=e, nazvanie='М', srok_proizvodstva_dney=20,
                                    srok_dostavki_dney=6, bufer_dney=4, status=Material.STATUS_NE_ZAKAZAN)
        self.assertTrue(m.prosrocheno)
        # заказанный материал просроченным не считается
        m.status = Material.STATUS_ZAKAZAN
        m.save(update_fields=['status'])
        self.assertFalse(Material.objects.get(pk=m.pk).prosrocheno)


class OplataTests(TestCase):
    def test_zashchita_ot_pereplaty(self):
        """ТЗ раздел 16: без явного флага объём к оплате не выше планового месяца."""
        b = make_brigada(); ob = make_objekt(b)
        o = OplataMontajnika(objekt=ob, montajnik_fio='И', rascenka=Decimal('300'),
                             mesyats=timezone.localdate().replace(day=1),
                             plan_objem_mesyats=Decimal('100'), fact_objem_mesyats=Decimal('130'))
        self.assertTrue(o.prevyshenie_grafika)
        self.assertEqual(o.objem_k_oplate, Decimal('100'))          # cap
        self.assertEqual(o.summa_k_oplate, Decimal('30000.00'))
        o.oplacheno_sverh_grafika = True
        self.assertEqual(o.objem_k_oplate, Decimal('130'))          # с флагом — факт


class DengiTests(TestCase):
    def test_garantiynoe_uderzhanie(self):
        b = make_brigada(); ob = make_objekt(b, garantiynoe_uderzhanie_procent=5)
        d = DvizhenieDeneg(objekt=ob, osnovanie='Этап', summa_nachislenie=Decimal('100000'),
                           data_plan=timezone.localdate())
        self.assertEqual(d.summa_za_vychetom_garantii, Decimal('95000.00'))

    def test_kassovy_razryv(self):
        b = make_brigada(); ob = make_objekt(b)
        DvizhenieDeneg.objects.create(objekt=ob, osnovanie='Аванс', summa_nachislenie=Decimal('50000'),
                                      data_plan=timezone.localdate(), status=DvizhenieDeneg.STATUS_POLUCHENO)
        RashodMesyachny.objects.create(objekt=ob, mesyats=timezone.localdate().replace(day=1),
                                       sutochnye=Decimal('80000'))
        ob = Objekt.objects.get(pk=ob.pk)
        self.assertEqual(ob.kassovy_razryv, Decimal('-30000.00'))
        self.assertTrue(ob.est_kassovy_razryv)


class SvetoforTests(TestCase):
    def test_otstavanie_zhyoltoe_ne_krasnoe(self):
        """ТЗ 7.6: отставание — жёлтый уровень, не красный."""
        b = make_brigada(); ob = make_objekt(b); T = timezone.localdate()
        # этап в разгаре, факт сильно ниже ожидаемого → отставание
        EtapGrafika.objects.create(objekt=ob, nazvanie='Э', plan_objem=Decimal('100'),
                                   fact_objem=Decimal('5'),
                                   plan_data_nachala=T - timedelta(days=10),
                                   plan_data_okonchania=T + timedelta(days=10))
        ob = Objekt.objects.get(pk=ob.pk)
        self.assertTrue(ob.zhyoltye_flagi)
        self.assertFalse(any('Отставание' in f for f in ob.krasnye_flagi))

    def test_prosrochka_materiala_krasnoe(self):
        b = make_brigada(); ob = make_objekt(b); T = timezone.localdate()
        e = EtapGrafika.objects.create(objekt=ob, nazvanie='Э', plan_objem=10, fact_objem=10,
                                       plan_data_nachala=T + timedelta(days=1),
                                       plan_data_okonchania=T + timedelta(days=5))
        Material.objects.create(objekt=ob, etap=e, nazvanie='М', srok_proizvodstva_dney=20,
                                srok_dostavki_dney=6, bufer_dney=4, status=Material.STATUS_NE_ZAKAZAN)
        ob = Objekt.objects.get(pk=ob.pk)
        self.assertTrue(any('Просрочен' in f for f in ob.krasnye_flagi))


class GrafikIzSmetyTests(TestCase):
    def test_etapy_sozdayutsya_iz_smety(self):
        b = make_brigada()
        sm = Smeta.objects.create(brigada=b, nazvanie='С', srok_dney=20)
        SmetaRabota.objects.create(smeta=sm, nazvanie='Демонтаж', kolvo=10, cena=300, poryadok=0)
        SmetaRabota.objects.create(smeta=sm, nazvanie='Штукатурка', kolvo=50, cena=500, poryadok=1)
        ob = make_objekt(b, smeta=sm)
        _create_etapy_from_smeta(ob, sm)
        self.assertEqual(ob.etapy.count(), 2)
        e = ob.etapy.first()
        self.assertEqual(e.plan_objem, Decimal('10'))
        self.assertEqual(e.rascenka, Decimal('300'))


class GatingAndAiTests(TestCase):
    def test_gejting_po_tarifu(self):
        self.assertFalse(limits.objekty_dostupny(make_brigada(tarif='start')))
        self.assertFalse(limits.objekty_dostupny(make_brigada(tarif='samozanyaty')))
        self.assertTrue(limits.objekty_dostupny(make_brigada(tarif='brigadir')))
        self.assertTrue(limits.objekty_dostupny(make_brigada(tarif='pro')))

    def test_limit_obektov(self):
        b = make_brigada(tarif='brigadir')  # лимит 3
        for i in range(3):
            make_objekt(b, nazvanie=f'О{i}')
        self.assertFalse(limits.mozhno_sozdat_obekt(b))

    def test_ai_demo_bez_klyucha(self):
        b = make_brigada(); ob = make_objekt(b)
        otvet, demo = ai_assistant.ask(ob, 'что горит?')
        self.assertTrue(demo)
        self.assertIn('Требует внимания', otvet)
