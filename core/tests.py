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

    ВАЖНО, почему тут заводятся объекты: первая версия теста открывала пустой дашборд,
    а календарь рисуется только `{% if kalendar %}`, то есть при наличии объектов. Из-за
    этого тест пропустил ровно ту же протечку в core/_kalendar_sobytie.html — комментарий
    печатался текстом в каждую ячейку календаря. Страница без данных ничего не сторожит:
    проверять надо ту разметку, которую видит пользователь.
    """

    STRANICY = ['/dashboard/', '/documents/', '/smety/', '/objekty/', '/objekty/postavki/',
                '/billing/', '/nalogi/', '/proverka/', '/market/', '/profile/']

    def setUp(self):
        from datetime import timedelta
        from decimal import Decimal
        from objekty.models import Objekt, EtapGrafika, Material, DvizhenieDeneg, OplataMontajnika
        T = timezone.localdate()
        # владельца заводит авто-вход, поэтому объекты цепляем к нему же
        self.client.get('/dashboard/')
        b = get_user_model().objects.get(username='vladelec').brigada
        ob = Objekt.objects.create(brigada=b, nazvanie='Объект', data_nachala=T,
                                   data_okonchania_plan=T + timedelta(days=60),
                                   summa_dogovora=Decimal('500000'))
        e = EtapGrafika.objects.create(objekt=ob, nazvanie='Стяжка', plan_objem=Decimal('10'),
                                       plan_data_nachala=T, plan_data_okonchania=T)
        Material.objects.create(objekt=ob, etap=e, nazvanie='Плитка', srok_proizvodstva_dney=5,
                                srok_dostavki_dney=3, bufer_dney=2)
        DvizhenieDeneg.objects.create(objekt=ob, osnovanie='Аванс', summa_nachislenie=Decimal('50000'),
                                      data_plan=T)
        OplataMontajnika.objects.create(objekt=ob, montajnik_fio='Петров', rascenka=Decimal('300'),
                                        mesyats=(T.replace(day=1) - timedelta(days=1)).replace(day=1),
                                        plan_objem_mesyats=Decimal('100'), fact_objem_mesyats=Decimal('100'))

    def test_net_syrogo_sintaksisa_shablonov(self):
        # Только {# и {% : `}}` и `{{` дают ложные срабатывания на инлайновом JS
        # (например, `catch(e){}})();` в шапке).
        for url in self.STRANICY:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                for marker in ('{#', '{%'):
                    self.assertNotIn(marker, html,
                                     f'на {url} в HTML протёк шаблонный тег {marker}')

    def test_kalendar_dejstvitelno_narisovan(self):
        """Страховка от того, что первый тест снова начнёт сторожить пустоту."""
        html = self.client.get('/dashboard/').content.decode()
        self.assertIn('Зарплата рабочим', html, 'календарь не отрисовался — проверять нечего')
        self.assertIn('Сдать: Стяжка', html)

    def test_ni_v_odnom_shablone_net_mnogostrochnyh_reshyotochnyh_kommentariev(self):
        """Проверка исходников, а не отрисовки.

        Проверка через HTML ловит протечку только в той ветке, которая отрисовалась на
        тестовых данных. Так уже дважды пропускали: комментарий в календаре виден лишь
        при наличии объектов, а комментарий в «ещё N» — лишь когда задач в дне больше
        трёх. Здесь ветки не важны: читаем сами файлы.
        """
        from pathlib import Path
        from django.conf import settings

        bity = []
        for shablon in Path(settings.BASE_DIR, 'templates').rglob('*.html'):
            for nomer, stroka in enumerate(shablon.read_text(encoding='utf-8').splitlines(), 1):
                if '{#' in stroka and '#}' not in stroka:
                    bity.append(f'{shablon.relative_to(settings.BASE_DIR)}:{nomer}')
        self.assertEqual(bity, [], 'многострочный {# #} не комментарий, а видимый текст на '
                                   'странице — используйте {% comment %}. Найдено: ' + ', '.join(bity))


class KalendarTests(TestCase):
    """Календарь месяца на дашборде: 4 вида задач по дням, просрочка — красным.

    Главное правило заказчика: задача горит красным, только если не выполнена И
    просрочена на день и более. Срок «сегодня» — ещё не просрочка.
    """

    def setUp(self):
        from datetime import timedelta
        from decimal import Decimal
        from objekty.models import Objekt, EtapGrafika, Material, DvizhenieDeneg, OplataMontajnika
        self.T = timezone.localdate()
        u = get_user_model().objects.create_user('kal', password='x')
        self.b = Brigada.objects.create(user=u, nazvanie='Т', telefon='+79990000000', tarif='pro',
                                        data_okonchaniya_tarifa=self.T + timedelta(days=30))
        self.ob = Objekt.objects.create(brigada=self.b, nazvanie='Объект', data_nachala=self.T,
                                        data_okonchania_plan=self.T + timedelta(days=60),
                                        summa_dogovora=Decimal('500000'))
        self.Material, self.Etap = Material, EtapGrafika
        self.Dengi, self.Oplata = DvizhenieDeneg, OplataMontajnika

    def _kalendar(self, god=None, mesyats=None):
        from core.dashboard import kalendar_mesyaca
        return kalendar_mesyaca(self.b, god, mesyats)

    def _sobytiya(self, kal, data):
        for n in kal['nedeli']:
            for d in n:
                if d['data'] == data:
                    return d['sobytiya']
        return None

    def _etap(self, okonchanie, fact=0, plan=10, nazvanie='Э'):
        from decimal import Decimal
        return self.Etap.objects.create(objekt=self.ob, nazvanie=nazvanie, plan_objem=Decimal(plan),
                                        fact_objem=Decimal(fact), plan_data_nachala=self.T,
                                        plan_data_okonchania=okonchanie)

    def test_setka_mesyaca_po_7_dney(self):
        kal = self._kalendar()
        self.assertTrue(all(len(n) == 7 for n in kal['nedeli']))
        # дни соседних месяцев помечены и не считаются «в месяце»
        vse = [d for n in kal['nedeli'] for d in n]
        self.assertTrue(any(not d['v_mesyatse'] for d in vse) or len(vse) == 28)
        self.assertTrue(any(d['segodnya'] for d in vse))

    def test_srok_segodnya_ne_prosrochen(self):
        """Граница правила: срок сегодня — ещё не горит."""
        self._etap(self.T)
        s = self._sobytiya(self._kalendar(), self.T)
        self.assertEqual(len(s), 1)
        self.assertFalse(s[0]['prosrocheno'])
        self.assertEqual(s[0]['cvet'], 'steel')

    def test_prosrochka_na_odin_den_gorit(self):
        """Срок вчера и не выполнено — красное."""
        from datetime import timedelta
        vchera = self.T - timedelta(days=1)
        self._etap(vchera)
        s = self._sobytiya(self._kalendar(vchera.year, vchera.month), vchera)
        self.assertTrue(s[0]['prosrocheno'])
        self.assertEqual(s[0]['cvet'], 'red')

    def test_vypolnennoe_ne_gorit_dazhe_v_proshlom(self):
        """Этап сдан на 100% — прошедшая дата не делает его красным."""
        from datetime import timedelta
        vchera = self.T - timedelta(days=1)
        self._etap(vchera, fact=10, plan=10)          # 100%
        s = self._sobytiya(self._kalendar(vchera.year, vchera.month), vchera)
        self.assertFalse(s[0]['prosrocheno'])
        self.assertTrue(s[0]['vypolneno'])

    def test_zakazanny_material_ne_gorit(self):
        from datetime import timedelta
        e = self._etap(self.T + timedelta(days=25))
        m = self.Material.objects.create(objekt=self.ob, etap=e, nazvanie='Плитка',
                                         srok_proizvodstva_dney=10, srok_dostavki_dney=5, bufer_dney=4,
                                         status=self.Material.STATUS_NE_ZAKAZAN)
        kraynyaya = m.data_zakaza_kraynyaya
        s = self._sobytiya(self._kalendar(kraynyaya.year, kraynyaya.month), kraynyaya)
        self.assertEqual(s[0]['tip'], 'material')
        # заказали — задача закрыта
        m.status = self.Material.STATUS_ZAKAZAN
        m.save(update_fields=['status'])
        s = self._sobytiya(self._kalendar(kraynyaya.year, kraynyaya.month), kraynyaya)
        self.assertTrue(s[0]['vypolneno'])
        self.assertFalse(s[0]['prosrocheno'])

    def test_poluchennye_dengi_ne_goryat(self):
        from datetime import timedelta
        from decimal import Decimal
        vchera = self.T - timedelta(days=1)
        d = self.Dengi.objects.create(objekt=self.ob, osnovanie='Аванс', summa_nachislenie=Decimal('50000'),
                                      data_plan=vchera, status=self.Dengi.STATUS_OZHIDAETSYA)
        s = self._sobytiya(self._kalendar(vchera.year, vchera.month), vchera)
        self.assertEqual(s[0]['tip'], 'dengi')
        self.assertTrue(s[0]['prosrocheno'])
        d.status = self.Dengi.STATUS_POLUCHENO
        d.save(update_fields=['status'])
        s = self._sobytiya(self._kalendar(vchera.year, vchera.month), vchera)
        self.assertFalse(s[0]['prosrocheno'])

    def test_zarplata_po_umolchaniyu_10_chislo_sleduyushchego(self):
        from datetime import date
        from decimal import Decimal
        self.Oplata.objects.create(objekt=self.ob, montajnik_fio='Петров', rascenka=Decimal('300'),
                                   mesyats=date(2026, 7, 1), plan_objem_mesyats=Decimal('100'),
                                   fact_objem_mesyats=Decimal('100'))
        s = self._sobytiya(self._kalendar(2026, 8), date(2026, 8, 10))
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]['tip'], 'zarplata')
        self.assertEqual(s[0]['cvet'], 'green')

    def test_zarplata_s_yavnoy_datoy_perekryvaet_umolchanie(self):
        from datetime import date
        from decimal import Decimal
        self.Oplata.objects.create(objekt=self.ob, montajnik_fio='Петров', rascenka=Decimal('300'),
                                   mesyats=date(2026, 7, 1), plan_objem_mesyats=Decimal('100'),
                                   fact_objem_mesyats=Decimal('100'), data_vyplaty=date(2026, 8, 5))
        kal = self._kalendar(2026, 8)
        self.assertEqual(self._sobytiya(kal, date(2026, 8, 10)), [],
                         'зарплата осталась на дате по умолчанию, хотя дата выплаты задана явно')
        s = self._sobytiya(kal, date(2026, 8, 5))
        self.assertEqual(s[0]['tip'], 'zarplata')

    def test_vyplachennaya_zarplata_ne_gorit(self):
        from datetime import date
        from decimal import Decimal
        self.Oplata.objects.create(objekt=self.ob, montajnik_fio='Петров', rascenka=Decimal('300'),
                                   mesyats=date(2020, 1, 1), plan_objem_mesyats=Decimal('100'),
                                   fact_objem_mesyats=Decimal('100'), summa_oplacheno=Decimal('30000'))
        s = self._sobytiya(self._kalendar(2020, 2), date(2020, 2, 10))
        self.assertTrue(s[0]['vypolneno'])
        self.assertFalse(s[0]['prosrocheno'])       # выплачено — не горит, хоть и 2020 год

    def test_chuzhie_zadachi_ne_popadayut(self):
        from datetime import timedelta
        from decimal import Decimal
        from objekty.models import Objekt
        u2 = get_user_model().objects.create_user('kal2', password='x')
        b2 = Brigada.objects.create(user=u2, nazvanie='Чужая', telefon='+79990000001', tarif='pro',
                                    data_okonchaniya_tarifa=self.T + timedelta(days=30))
        ob2 = Objekt.objects.create(brigada=b2, nazvanie='Чужой', data_nachala=self.T,
                                    data_okonchania_plan=self.T + timedelta(days=60),
                                    summa_dogovora=Decimal('100000'))
        self.Etap.objects.create(objekt=ob2, nazvanie='Чужой этап', plan_objem=Decimal('10'),
                                 plan_data_nachala=self.T, plan_data_okonchania=self.T)
        self.assertEqual(self._kalendar()['vsego'], 0)

    def test_schetchik_prosrochennyh(self):
        from datetime import timedelta
        vchera = self.T - timedelta(days=1)
        self._etap(vchera)
        self._etap(vchera)
        self._etap(self.T)                      # сегодня — не считается
        kal = self._kalendar(vchera.year, vchera.month)
        self.assertEqual(kal['prosrocheno'], 2)

    def test_kalendar_na_stranice(self):
        self._etap(self.T)
        self.client.force_login(self.b.user)
        r = self.client.get(reverse('core:dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Заказ материала')      # легенда
        self.assertContains(r, 'Зарплата рабочим')

    def test_vse_zadachi_dnya_dostizhimy(self):
        """В ячейке дня видно 3 задачи, остальные — под «ещё N», но в HTML они есть.

        Все зарплаты месяца падают на одно число, поэтому переполненный день — норма,
        а не край. Раньше «ещё 13» было мёртвой надписью, и 13 задач из 16 достать
        было нельзя.
        """
        for i in range(6):
            self._etap(self.T, nazvanie=f'Стяжка{i}')      # 6 задач на один день
        self.client.force_login(self.b.user)
        html = self.client.get(reverse('core:dashboard')).content.decode()
        self.assertIn('ещё 3', html)
        self.assertIn('<details>', html)
        # все шесть — в разметке, а не только первые три
        for i in range(6):
            self.assertIn(f'Сдать: Стяжка{i}', html,
                          f'задача «Стяжка{i}» не попала в HTML — её не достать')

    def test_listanie_mesyacev(self):
        self.client.force_login(self.b.user)
        r = self.client.get(reverse('core:dashboard'), {'god': 2026, 'mesyats': 12})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['kalendar']['nazvanie'], 'Декабрь 2026')
        self.assertEqual(r.context['kalendar']['sled'], {'god': 2027, 'mesyats': 1})
        self.assertEqual(r.context['kalendar']['pred'], {'god': 2026, 'mesyats': 11})

    def test_musor_v_parametrah_ne_lomaet(self):
        """Кривые ?god/?mesyats не должны валить дашборд — просто текущий месяц."""
        self.client.force_login(self.b.user)
        for params in ({'god': 'abc'}, {'mesyats': '13'}, {'mesyats': '0'}, {'god': '1'}):
            with self.subTest(params=params):
                r = self.client.get(reverse('core:dashboard'), params)
                self.assertEqual(r.status_code, 200)


@override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
class MenyuTests(TestCase):
    """Навигация на телефоне. Ниже lg полное меню в шапке не помещается, и до этого
    уйти с любой страницы кроме дашборда было некуда — только через логотип."""

    def test_menyu_est_na_kazhdoy_stranice(self):
        for url in ('/dashboard/', '/documents/', '/smety/', '/objekty/', '/nalogi/', '/profile/'):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn('data-menyu', html, f'на {url} нет выдвижного меню — с неё не уйти')

    def test_v_menyu_vse_razdely(self):
        from core.context_processors import RAZDELY
        html = self.client.get('/documents/').content.decode()
        for _, nazvanie, _ in RAZDELY:
            self.assertIn(nazvanie, html, f'раздела «{nazvanie}» нет в меню')

    def test_est_vyhod(self):
        """Ниже lg «Выйти» убран из шапки, значит он обязан быть в меню."""
        html = self.client.get('/documents/').content.decode()
        self.assertIn('/logout/', html)
        self.assertIn('Выйти', html)

    def test_spisok_razdelov_ne_bityy(self):
        """Все имена маршрутов в RAZDELY должны разрешаться."""
        from django.urls import reverse, NoReverseMatch
        from core.context_processors import RAZDELY
        for imya, nazvanie, _ in RAZDELY:
            with self.subTest(razdel=nazvanie):
                try:
                    reverse(imya)
                except NoReverseMatch:
                    self.fail(f'битая ссылка в меню: {imya} («{nazvanie}»)')

    def test_anonimu_menyu_ne_dayotsya(self):
        """Публичная смета не должна звать заказчика в кабинет владельца."""
        from core.context_processors import menyu
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        r = RequestFactory().get('/s/abc/')
        r.user = AnonymousUser()
        self.assertEqual(menyu(r), {})


@override_settings(AUTO_LOGIN=True, AUTO_LOGIN_USERNAME='vladelec')
class ShriftySvoiTests(TestCase):
    """Шрифты обязаны отдаваться со своего сервера.

    Google Fonts CDN получает IP каждого посетителя (в ЕС за это штрафовали, у нас —
    152-ФЗ). Плюс внешняя зависимость: чужой сервер в критическом пути отрисовки.
    """

    def test_net_obrashcheniy_k_google_fonts(self):
        for url in ('/dashboard/', '/documents/', '/profile/'):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('fonts.googleapis.com', html,
                                 'шрифты снова тянутся с Google CDN — он видит IP посетителя')
                self.assertNotIn('fonts.gstatic.com', html)

    def test_shrifty_lezhat_ryadom(self):
        from pathlib import Path
        from django.conf import settings
        fonts = Path(settings.BASE_DIR, 'static', 'fonts')
        est = {f.name for f in fonts.glob('*.woff2')}
        for nuzhen in ('inter-cyrillic.woff2', 'inter-latin.woff2',
                       'manrope-cyrillic.woff2', 'manrope-latin.woff2'):
            self.assertIn(nuzhen, est, f'нет файла шрифта {nuzhen} — интерфейс сядет на запасной')

    def test_sw_kladyot_shrifty_v_offlain_kesh(self):
        """Иначе офлайн интерфейс остаётся без гарнитур.

        Имена ищем по префиксу: после collectstatic они хешированы
        (fonts.cc81a10e3d9e.css), а без него — обычные.
        """
        sw = self.client.get('/sw.js').content.decode()
        self.assertIn('/static/fonts/inter-cyrillic', sw)
        self.assertIn('/static/fonts/manrope-cyrillic', sw)
        self.assertIn('/static/css/fonts.', sw)
        self.assertNotIn('fonts.gstatic.com', sw)


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
