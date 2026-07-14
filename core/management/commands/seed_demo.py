# -*- coding: utf-8 -*-
"""
Демо-наполнение: вымышленная тюменская бригада «СибСтрой 72» и по 8–10 полностью
заполненных записей в каждом разделе (документы, расчёты, сметы, объекты Модуля J,
платежи) на реальных адресах строек Тюмени с вымышленными данными.

Запуск:  python manage.py seed_demo
Идемпотентно: перед наполнением очищает прежние демо-данные этой бригады.
Логин демо-фирмы: demo / Demo12345
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Brigada
from documents.models import Dokument, DokumentPozicia
from documents.pdf import render_pdf
from calculator.models import Raschet
from smety.models import Smeta, SmetaRabota, BazaCen
from smety.pdf import render_smeta_pdf
from billing.models import Platezh
from objekty.models import (
    Objekt, EtapGrafika, Material, OplataMontajnika, RashodMesyachny, DvizhenieDeneg, AiZapros,
)
from podpis.models import PodpisZakazchika
from nalogi.models import ChekFNS, NalogOtchet
from nalogi import fns as fns_service
from proverka.models import ProverkaZakazchika, ChyornySpisok
from proverka import service as proverka_service
from messengers.models import WhatsAppOtpravka, TelegramUser
from messengers import wa as wa_service
from golos.models import GolosovayaKomanda

User = get_user_model()

# Реальные адреса/ЖК Тюмени (данные по объектам — вымышленные)
ADRESA = [
    'г. Тюмень, ул. Мельникайте, 137, кв. 84',
    'г. Тюмень, ЖК «Преображенский», ул. Николая Зелинского, 21, кв. 156',
    'г. Тюмень, ЖК «Юговской», Тихий бульвар, 3, кв. 42',
    'г. Тюмень, ул. Республики, 92, кв. 210',
    'г. Тюмень, ул. Широтная, 158, кв. 33',
    'г. Тюмень, ул. Пермякова, 46, кв. 118',
    'г. Тюмень, ЖК «Новин», ул. Первооткрывателей, 12, кв. 75',
    'г. Тюмень, ул. Федюнинского, 56, кв. 9',
    'г. Тюмень, ЖК «Айвазовский», ул. Ивана Крылова, 8, кв. 64',
    'г. Тюмень, мкр. Ямальский-2, ул. Обская, 21, кв. 147',
    'г. Тюмень, ул. 50 лет Октября, 62, кв. 12',
    'г. Тюмень, ЖК «Европейский», ул. Максима Горького, 83, кв. 201',
]

ZAKAZCHIKI = [
    ('Кузнецов Иван Петрович', '+79088410011'),
    ('Медведева Ольга Сергеевна', '+79129320022'),
    ('Абрамов Сергей Николаевич', '+79224110033'),
    ('Фомина Наталья Андреевна', '+79825610044'),
    ('Захаров Дмитрий Олегович', '+79088710055'),
    ('Титова Елена Владимировна', '+79323410066'),
    ('Соколов Артём Игоревич', '+79044910077'),
    ('Белова Марина Юрьевна', '+79129110088'),
    ('Григорьев Павел Викторович', '+79224510099'),
    ('Никитина Алёна Романовна', '+79825910100'),
    ('Морозов Константин Львович', '+79088010111'),
    ('Лебедева Ирина Дмитриевна', '+79323910122'),
]

MASTERA = ['Ковалёв А.С.', 'Мухаметшин Р.Р.', 'Дьяченко В.П.', 'Устинов О.Н.', 'Баширов Т.М.']
MONTAJNIKI = ['Гафуров Р.', 'Смирнов К.', 'Ли Вэй', 'Оганесян А.', 'Петров Д.', 'Юсупов И.']


class Command(BaseCommand):
    help = 'Наполняет демо-фирму «СибСтрой 72» реалистичными данными (Тюмень).'

    def handle(self, *args, **options):
        random.seed(72)
        self.today = timezone.localdate()
        brigada = self._firm()
        self._wipe(brigada)
        self._payments(brigada)
        self._documents(brigada)
        self._calculations(brigada)
        smety = self._estimates(brigada)
        self._objects(brigada, smety)
        self._addendum(brigada)
        self.stdout.write(self.style.SUCCESS(
            '\nДемо-данные созданы для бригады «%s». Вход: demo / Demo12345' % brigada.nazvanie
        ))

    # ------------------------------------------------------------------ фирма
    def _firm(self):
        user, created = User.objects.get_or_create(username='demo', defaults={'first_name': 'Демо'})
        user.set_password('Demo12345')
        user.save()
        brigada, _ = Brigada.objects.get_or_create(user=user, defaults={'nazvanie': 'СибСтрой 72'})
        brigada.nazvanie = 'Бригада «СибСтрой 72»'
        brigada.telefon = '+79088417272'
        brigada.region = 'Тюмень'
        brigada.rekvizity = (
            'ИП Ковалёв Артём Сергеевич\n'
            'ИНН 720312345678 · ОГРНИП 320723200012345\n'
            'р/с 40802810067100012345 в Тюменском отделении №29 ПАО Сбербанк\n'
            'к/с 30101810800000000651 · БИК 047102651\n'
            'г. Тюмень, ул. 30 лет Победы, 88'
        )
        brigada.tarif = 'pro'
        brigada.data_okonchaniya_tarifa = self.today + timedelta(days=180)
        brigada.save()
        self.stdout.write('Фирма: %s (тариф PRO)' % brigada.nazvanie)
        return brigada

    def _wipe(self, brigada):
        Dokument.objects.filter(brigada=brigada).delete()  # каскадом: чеки, подписи, WA, фото
        Raschet.objects.filter(brigada=brigada).delete()
        Smeta.objects.filter(brigada=brigada).delete()
        Objekt.objects.filter(brigada=brigada).delete()
        Platezh.objects.filter(brigada=brigada).delete()
        brigada.limit_trackers.all().delete()
        ProverkaZakazchika.objects.filter(brigada=brigada).delete()
        NalogOtchet.objects.filter(brigada=brigada).delete()
        GolosovayaKomanda.objects.filter(brigada=brigada).delete()
        ChyornySpisok.objects.all().delete()

    # --------------------------------------------------------------- платежи
    def _payments(self, brigada):
        plan = [
            ('samozanyaty', 490, 95), ('samozanyaty', 490, 65), ('brigadir', 990, 55),
            ('brigadir', 990, 25), ('brigadir', 990, 5), ('pro', 1990, 3),
        ]
        for tarif, summa, days_ago in plan:
            p = Platezh.objects.create(
                brigada=brigada, summa=Decimal(summa), tarif=tarif,
                status=Platezh.STATUS_OPLACHEN, yookassa_id='demo-%d' % random.randint(10**11, 10**12),
                demo_rezhim=False,
            )
            Platezh.objects.filter(pk=p.pk).update(data=timezone.now() - timedelta(days=days_ago))
        # один ожидающий и один возврат — для наглядности статусов
        Platezh.objects.create(brigada=brigada, summa=Decimal('1990'), tarif='pro',
                               status=Platezh.STATUS_OZHIDAET, yookassa_id='demo-pending-1')
        Platezh.objects.create(brigada=brigada, summa=Decimal('490'), tarif='samozanyaty',
                               status=Platezh.STATUS_VOZVRAT, yookassa_id='demo-refund-1')
        self.stdout.write('Платежи: 8')

    # -------------------------------------------------------------- документы
    def _documents(self, brigada):
        T = self.today
        specs = [
            dict(tip='dogovor', i=0, summa=485000, d0=-14, d1=32),
            dict(tip='dogovor', i=1, summa=228000, d0=-3, d1=28),
            dict(tip='dogovor', i=8, summa=340000, d0=5, d1=47),
            dict(tip='raspiska', i=4, avans=150000, d0=-10),
            dict(tip='raspiska', i=5, avans=90000, d0=-2),
            dict(tip='akt_priemki', i=6, etap='Черновая отделка: штукатурка и стяжка'),
            dict(tip='akt_priemki', i=7, etap='Электромонтаж: разводка и щиток'),
            dict(tip='akt_vkr', i=3, d1=-1, works=[
                ('Демонтаж перегородок', 'м²', 24, 350),
                ('Штукатурка стен по маякам', 'м²', 96, 520),
                ('Стяжка пола полусухая', 'м²', 58, 480),
                ('Электромонтаж (точки)', 'шт', 42, 650),
                ('Укладка плитки', 'м²', 34, 1200),
            ]),
            dict(tip='akt_vkr', i=10, d1=-6, works=[
                ('Монтаж ГКЛ потолка', 'м²', 46, 780),
                ('Поклейка обоев', 'м²', 132, 320),
                ('Установка дверей', 'шт', 5, 2500),
                ('Сантехнические работы', 'шт', 8, 1800),
            ]),
            dict(tip='dogovor', i=9, summa=612000, d0=-1, d1=60),
        ]
        tpl = {
            'dogovor': 'documents/pdf/dogovor.html',
            'raspiska': 'documents/pdf/raspiska.html',
            'akt_priemki': 'documents/pdf/akt_priemki.html',
            'akt_vkr': 'documents/pdf/akt_vkr.html',
        }
        n = 0
        for s in specs:
            zak, tel = ZAKAZCHIKI[s['i']]
            d = Dokument(brigada=brigada, tip=s['tip'], zakazchik=zak, zakazchik_telefon=tel,
                         adres_obekta=ADRESA[s['i']])
            if s['tip'] == 'dogovor':
                d.summa = Decimal(s['summa'])
                d.srok_nachala = T + timedelta(days=s['d0'])
                d.srok_okonchania = T + timedelta(days=s['d1'])
            elif s['tip'] == 'raspiska':
                d.avans_summa = Decimal(s['avans'])
                d.srok_nachala = T + timedelta(days=s['d0'])
            elif s['tip'] == 'akt_priemki':
                d.etap_nazvanie = s['etap']
                d.checklist = Dokument.DEFAULT_CHECKLIST
            elif s['tip'] == 'akt_vkr':
                d.srok_okonchania = T + timedelta(days=s['d1'])
            d.save()
            if s['tip'] == 'akt_vkr':
                for nm, ed, kol, cena in s['works']:
                    DokumentPozicia.objects.create(dokument=d, nazvanie=nm, edinica=ed,
                                                   kolvo=Decimal(kol), cena=Decimal(cena))
            self._attach_doc_pdf(d, tpl[s['tip']], brigada)
            n += 1
        self.stdout.write('Документы: %d (с PDF)' % n)

    def _attach_doc_pdf(self, d, template, brigada):
        ctx = {'d': d, 'brigada': brigada,
               'pozicii': d.pozicii.all() if d.tip == 'akt_vkr' else None,
               'checklist': d.checklist, 'is_free_tier': False}
        try:
            pdf = render_pdf(template, ctx)
            if pdf:
                d.pdf_file.save('%s.pdf' % d.nomer, ContentFile(pdf), save=True)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write('  PDF документа %s не сформирован: %s' % (d.nomer, exc))

    # -------------------------------------------------------------- расчёты
    def _calculations(self, brigada):
        rows = [
            dict(ploshad=42, tip='komfort', rab=2, dni=18, stavka=3200, arenda=8000, dostavka=6000, rashod=4000, nalog='4'),
            dict(ploshad=68, tip='econom', rab=3, dni=25, stavka=3000, arenda=12000, dostavka=9000, rashod=5000, nalog='6'),
            dict(ploshad=95, tip='premium', rab=4, dni=40, stavka=3800, arenda=25000, dostavka=18000, rashod=9000, nalog='6'),
            dict(ploshad=8, tip='komfort', rab=1, dni=6, stavka=3500, arenda=3000, dostavka=2500, rashod=1500, nalog='4'),
            dict(ploshad=54, tip='komfort', rab=2, dni=22, stavka=3300, arenda=10000, dostavka=7000, rashod=4500, nalog='4'),
            dict(ploshad=120, tip='premium', rab=5, dni=55, stavka=4000, arenda=40000, dostavka=30000, rashod=15000, nalog='6'),
            dict(ploshad=36, tip='econom', rab=2, dni=14, stavka=2800, arenda=5000, dostavka=4000, rashod=3000, nalog='0'),
            dict(ploshad=61, tip='komfort', rab=3, dni=28, stavka=3400, arenda=14000, dostavka=11000, rashod=6000, nalog='4'),
            dict(ploshad=78, tip='premium', rab=4, dni=45, stavka=3900, arenda=30000, dostavka=22000, rashod=12000, nalog='6'),
            dict(ploshad=15, tip='komfort', rab=1, dni=9, stavka=3600, arenda=4000, dostavka=3500, rashod=2000, nalog='4'),
        ]
        for r in rows:
            Raschet.objects.create(
                brigada=brigada, ploshad=Decimal(r['ploshad']), tip_remonta=r['tip'],
                kolvo_rabochih=r['rab'], dni=r['dni'], stavka_v_den=Decimal(r['stavka']),
                arenda=Decimal(r['arenda']), dostavka=Decimal(r['dostavka']),
                rashodniki=Decimal(r['rashod']), nalog=r['nalog'],
            )
        self.stdout.write('Расчёты: %d' % len(rows))

    # ---------------------------------------------------------------- сметы
    def _estimates(self, brigada):
        baza = list(BazaCen.objects.all())
        nazvaniya = [
            ('Ремонт 2-комнатной квартиры под ключ', 0, 'srednyaya', True),
            ('Косметический ремонт студии', 2, 'econom', True),
            ('Премиум-ремонт 3-комнатной', 8, 'premium', True),
            ('Ремонт санузла под ключ', 5, 'srednyaya', False),
            ('Отделка новостройки, черновая', 6, 'econom', False),
            ('Ремонт кухни-гостиной', 3, 'srednyaya', True),
            ('Электромонтаж квартиры', 7, 'srednyaya', False),
            ('Ремонт коридора и прихожей', 4, 'econom', False),
            ('Комплексная отделка 1-комнатной', 10, 'srednyaya', True),
            ('Ремонт детской комнаты', 11, 'premium', False),
        ]
        created = []
        for name, ai, uroven, publish in nazvaniya:
            zak, _ = ZAKAZCHIKI[ai]
            smeta = Smeta.objects.create(
                brigada=brigada, nazvanie=name, adres=ADRESA[ai], zakazchik=zak,
                urovne_cen=uroven, srok_dney=random.randint(14, 55),
            )
            k = random.randint(6, 11)
            for j, b in enumerate(random.sample(baza, min(k, len(baza)))):
                SmetaRabota.objects.create(
                    smeta=smeta, baza_cen=b, nazvanie=b.nazvanie, edinica=b.edinica,
                    kolvo=Decimal(random.randint(4, 60)), cena=b.cena_dlya_urovnya(uroven), poryadok=j,
                )
            if publish:
                smeta.status = 'public'
                smeta.ensure_public_slug()
            self._attach_smeta_pdf(smeta)
            created.append(smeta)
        self.stdout.write('Сметы: %d (с PDF, опубликовано %d)' % (len(created), sum(1 for _, _, _, p in nazvaniya if p)))
        return created

    def _attach_smeta_pdf(self, smeta):
        ctx = {'s': smeta, 'brigada': smeta.brigada, 'raboty': smeta.raboty.all(), 'is_free_tier': False}
        try:
            pdf = render_smeta_pdf(ctx)
            if pdf:
                smeta.pdf_file.save('%s.pdf' % smeta.nomer, ContentFile(pdf), save=True)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write('  PDF сметы %s не сформирован: %s' % (smeta.nomer, exc))

    # -------------------------------------------------------------- объекты J
    def _objects(self, brigada, smety):
        T = self.today
        # (адрес_idx, статус, срок_дней, флаг_сценария)
        specs = [
            (0, 'active', 45, 'overdue_material'),   # красный: просрочен материал + разрыв
            (1, 'active', 40, 'on_track'),           # зелёный
            (2, 'active', 60, 'behind'),             # жёлтый: отставание
            (3, 'active', 35, 'overpay'),            # красный: риск переплаты
            (4, 'active', 30, 'on_track'),           # зелёный
            (5, 'paused', 50, 'order_soon'),         # материал заказать в 7 дней
            (7, 'active', 42, 'cash_gap'),           # красный: кассовый разрыв
            (8, 'completed', 38, 'done'),            # сдан
            (10, 'active', 33, 'on_track'),          # зелёный
            (11, 'active', 55, 'overdue_material'),  # красный
        ]
        etap_shablon = [
            ('Демонтажные работы', 'м²', 40, 900),
            ('Черновая отделка стен', 'м²', 110, 620),
            ('Стяжка и полы', 'м²', 62, 700),
            ('Электрика и слаботочка', 'точка', 48, 850),
            ('Чистовая отделка', 'м²', 105, 950),
            ('Плитка и сантехника', 'м²', 28, 1400),
        ]
        for k, (ai, status, srok, scenario) in enumerate(specs):
            zak, _ = ZAKAZCHIKI[ai]
            smeta = smety[k] if k < len(smety) else None
            summa = Decimal(random.randint(380, 950) * 1000)
            ob = Objekt.objects.create(
                brigada=brigada, smeta=smeta, nazvanie='Объект: %s' % ADRESA[ai].split(', ', 1)[1],
                adres=ADRESA[ai], zakazchik=zak, master_otvetstvenny=random.choice(MASTERA),
                data_nachala=T - timedelta(days=srok // 2),
                data_okonchania_plan=T + timedelta(days=srok // 2),
                summa_dogovora=summa, avans_procent=30,
                srok_oplaty_posle_akta_dney=10, garantiynoe_uderzhanie_procent=5,
                status=status,
            )
            self._object_body(ob, etap_shablon, scenario)
        self.stdout.write('Объекты (Модуль J): %d' % len(specs))

    def _object_body(self, ob, etap_shablon, scenario):
        T = self.today
        n_etap = random.randint(4, 6)
        etapy = []
        cursor = ob.data_nachala
        for i in range(n_etap):
            nm, ed, plan, rasc = etap_shablon[i]
            dur = random.randint(7, 14)
            nachalo = cursor
            okonchanie = nachalo + timedelta(days=dur)
            # факт: зависит от сценария и от того, прошёл ли этап
            if scenario == 'done':
                fact = Decimal(plan)
            elif okonchanie < T:
                fact = Decimal(plan)                         # прошлые этапы закрыты
            elif nachalo <= T <= okonchanie:
                total = (okonchanie - nachalo).days or 1
                frac = min(max((T - nachalo).days / total, 0.15), 1)
                if scenario == 'behind':
                    frac = frac * 0.25   # явное отставание: факт сильно ниже ожидаемого темпа
                fact = (Decimal(plan) * Decimal(str(round(frac, 2)))).quantize(Decimal('0.01'))
            else:
                fact = Decimal(0)                            # будущие
            e = EtapGrafika.objects.create(
                objekt=ob, nazvanie=nm, edinica=ed, plan_objem=Decimal(plan),
                fact_objem=fact, rascenka=Decimal(rasc),
                plan_data_nachala=nachalo, plan_data_okonchania=okonchanie, poryadok=i,
            )
            etapy.append(e)
            cursor = okonchanie

        # Материалы
        mat_names = ['Плитка керамогранит', 'Ламинат 33 класс', 'Двери межкомнатные',
                     'Радиаторы отопления', 'Смесители и сантехника', 'Гипсокартон Knauf']
        for i, e in enumerate(etapy[:4]):
            nm = mat_names[i % len(mat_names)]
            if scenario == 'overdue_material' and i == 0:
                # крайняя дата в прошлом, не заказан -> просрочка (этап впереди, факт 0)
                e.plan_data_nachala = T + timedelta(days=3); e.fact_objem = Decimal(0); e.save()
                Material.objects.create(objekt=ob, etap=e, nazvanie=nm,
                                        srok_proizvodstva_dney=20, srok_dostavki_dney=7, bufer_dney=4,
                                        status=Material.STATUS_NE_ZAKAZAN)
            elif scenario == 'order_soon' and i == 0:
                e.plan_data_nachala = T + timedelta(days=10); e.fact_objem = Decimal(0); e.save()
                Material.objects.create(objekt=ob, etap=e, nazvanie=nm,
                                        srok_proizvodstva_dney=3, srok_dostavki_dney=2, bufer_dney=1,
                                        status=Material.STATUS_NE_ZAKAZAN)
            else:
                st = random.choice([Material.STATUS_ZAKAZAN, Material.STATUS_V_PUTI, Material.STATUS_NA_OBEKTE])
                Material.objects.create(
                    objekt=ob, etap=e, nazvanie=nm, srok_proizvodstva_dney=random.randint(5, 15),
                    srok_dostavki_dney=random.randint(2, 7), bufer_dney=4, status=st,
                    data_zakaza_fakt=T - timedelta(days=random.randint(1, 20)),
                )

        # Оплата монтажникам (2-3 записи)
        mesyats1 = T.replace(day=1)
        for j in range(random.randint(2, 3)):
            plan_v = Decimal(random.randint(40, 120))
            if scenario == 'overpay' and j == 0:
                fact_v = plan_v + Decimal(random.randint(15, 40))   # факт > плана без подтверждения
                sverh = False
            else:
                fact_v = plan_v * Decimal(random.choice(['0.6', '0.8', '1.0']))
                sverh = False
            rasc = Decimal(random.randint(280, 420))
            OplataMontajnika.objects.create(
                objekt=ob, montajnik_fio=random.choice(MONTAJNIKI), rascenka=rasc,
                mesyats=mesyats1, plan_objem_mesyats=plan_v, fact_objem_mesyats=fact_v,
                oplacheno_sverh_grafika=sverh,
                summa_oplacheno=(min(fact_v, plan_v) * rasc) * Decimal(random.choice(['0.5', '0.7', '1.0'])),
            )

        # Расходы (1-2 месяца)
        for off in range(random.randint(1, 2)):
            m = (mesyats1 - timedelta(days=31 * off)).replace(day=1)
            RashodMesyachny.objects.create(
                objekt=ob, mesyats=m,
                sutochnye=Decimal(random.randint(15, 35) * 1000),
                arenda_kvartiry=Decimal(random.randint(18, 30) * 1000),
                oplata_mastera=Decimal(random.randint(40, 70) * 1000),
                dolya_ofisa=Decimal(random.randint(3, 8) * 1000),
                prochee=Decimal(random.randint(2, 10) * 1000),
            )

        # Движение денег — сценарно: у «здоровых» объектов приход перекрывает расход
        # (зелёные карточки), у cash_gap/overdue_material аванс не получен (красные).
        rashod_now = ob.rashod_itogo
        avans = (ob.summa_dogovora * ob.avans_procent / 100).quantize(Decimal('1'))
        etap_sum = ((ob.summa_dogovora - avans) / max(len(etapy), 1)).quantize(Decimal('1'))
        zdorovy = scenario not in ('cash_gap', 'overdue_material')

        if zdorovy:
            DvizhenieDeneg.objects.create(
                objekt=ob, osnovanie='Аванс по договору', summa_nachislenie=avans,
                data_plan=ob.data_nachala, data_fakt=ob.data_nachala,
                status=DvizhenieDeneg.STATUS_POLUCHENO,
            )
            # закрытые этапы оплачены — гарантируем, что приход > расхода
            poluchennye = avans
            for i, e in enumerate(etapy):
                if e.plan_data_okonchania >= T:
                    break
                DvizhenieDeneg.objects.create(
                    objekt=ob, etap=e, osnovanie='Оплата за этап «%s»' % e.nazvanie,
                    summa_nachislenie=etap_sum,
                    data_plan=e.plan_data_okonchania + timedelta(days=ob.srok_oplaty_posle_akta_dney),
                    data_fakt=e.plan_data_okonchania + timedelta(days=5),
                    status=DvizhenieDeneg.STATUS_POLUCHENO,
                )
                poluchennye += etap_sum
            # если расход всё же обгоняет приход — добор «этапным» платежом
            if poluchennye <= rashod_now:
                DvizhenieDeneg.objects.create(
                    objekt=ob, osnovanie='Оплата за принятый этап',
                    summa_nachislenie=(rashod_now - poluchennye + etap_sum).quantize(Decimal('1')),
                    data_plan=T - timedelta(days=3), data_fakt=T - timedelta(days=1),
                    status=DvizhenieDeneg.STATUS_POLUCHENO,
                )
            # плюс ближайший ожидаемый платёж
            DvizhenieDeneg.objects.create(
                objekt=ob, osnovanie='Оплата за текущий этап', summa_nachislenie=etap_sum,
                data_plan=T + timedelta(days=14), status=DvizhenieDeneg.STATUS_OZHIDAETSYA,
            )
        else:
            # красный сценарий: аванс ещё не получен, есть просроченный платёж
            DvizhenieDeneg.objects.create(
                objekt=ob, osnovanie='Аванс по договору', summa_nachislenie=avans,
                data_plan=ob.data_nachala, status=DvizhenieDeneg.STATUS_PROSROCHENO,
            )
            for i, e in enumerate(etapy[:2]):
                if e.plan_data_okonchania < T:
                    DvizhenieDeneg.objects.create(
                        objekt=ob, etap=e, osnovanie='Оплата за этап «%s»' % e.nazvanie,
                        summa_nachislenie=etap_sum,
                        data_plan=e.plan_data_okonchania + timedelta(days=ob.srok_oplaty_posle_akta_dney),
                        status=DvizhenieDeneg.STATUS_PROSROCHENO,
                    )

        # Диалог с AI-ассистентом (демо-сводка) — 1-2 на объект
        from objekty import ai_assistant
        for vopros in ['Что горит по объекту прямо сейчас?', 'Успеваем ли мы по графику и деньгам?'][:random.randint(1, 2)]:
            otvet, demo = ai_assistant.ask(ob, vopros)
            AiZapros.objects.create(objekt=ob, vopros=vopros, otvet=otvet, demo_rezhim=demo)

    # ------------------------------------------------ модули D–I (Addendum №1)
    def _addendum(self, brigada):
        dokumenty = list(Dokument.objects.filter(brigada=brigada))
        income = [d for d in dokumenty if d.tip in ('dogovor', 'raspiska', 'akt_vkr')]
        akty = [d for d in dokumenty if d.tip == 'akt_priemki']

        # Чёрный список (Модуль E) — вымышленные проблемные контрагенты
        ChyornySpisok.objects.create(telefon=ZAKAZCHIKI[10][1], prichina='Не оплатил финальный этап, 90 000 ₽', istochnik='narod', kolvo_zhalob=4)
        ChyornySpisok.objects.create(inn='7203555001', prichina='3 арбитражных дела по неоплате подряда', istochnik='arbitr', kolvo_zhalob=3)
        ChyornySpisok.objects.create(telefon='+79111234500', prichina='Отказ от приёмки без оснований', istochnik='narod', kolvo_zhalob=2)

        # Чеки ФНС (Модуль D) — пробиваем по документам-основаниям + сводка
        n_chek = 0
        for d in income[:6]:
            chek = ChekFNS(brigada=brigada, dokument=d, summa=(d.avans_summa or d.summa or Decimal('50000')),
                           naznachenie=f'Оплата по документу №{d.nomer}', telefon_zakazchika=d.zakazchik_telefon)
            fns_service.probit_chek(chek)
            n_chek += 1
        for i in range(2):
            chek = ChekFNS(brigada=brigada, summa=Decimal(random.randint(20, 80) * 1000),
                           naznachenie='Оплата за работы наличными', telefon_zakazchika=random.choice(ZAKAZCHIKI)[1])
            fns_service.probit_chek(chek)
            n_chek += 1

        # Проверки заказчиков (Модуль E) — разный риск, включая чёрный список
        proverki_vhod = [
            ('telefon', ZAKAZCHIKI[10][1]), ('inn', '7203555001'),   # высокий (чёрный список)
            ('inn', '7203123456'), ('inn', '7204998877'),
            ('telefon', ZAKAZCHIKI[1][1]), ('telefon', ZAKAZCHIKI[3][1]),
        ]
        for tip, znach in proverki_vhod:
            risk, prichina, detali, demo = proverka_service.proverit(tip, znach)
            ProverkaZakazchika.objects.create(brigada=brigada, tip_poiska=tip, znachenie=znach,
                                              status_riska=risk, prichina=prichina, detali=detali, demo_rezhim=demo)

        # Подписи ПЭП (Модуль I) — часть подписана, часть ожидает
        for i, d in enumerate(income[:5]):
            p = PodpisZakazchika.objects.create(dokument=d)
            if i < 3:
                p.podpisat(telefon=d.zakazchik_telefon or '+79990000000', ip=f'85.140.{random.randint(1,254)}.{random.randint(1,254)}')

        # WhatsApp-отправки (Модуль F)
        for d in income[:5]:
            wa_service.otpravit(d, d.zakazchik_telefon or '+79990001111', WhatsAppOtpravka.TIP_DOKUMENT,
                                f'{brigada.nazvanie}: направляем документ №{d.nomer}')
        if income:
            wa_service.otpravit(income[0], income[0].zakazchik_telefon or '+79990001111',
                                WhatsAppOtpravka.TIP_PODPIS, 'Ссылка на подписание')

        # Telegram — привязан (демо)
        tg = TelegramUser.dlya_brigady(brigada)
        tg.telegram_id = 100200300
        tg.username = 'sibstroy72'
        tg.status = TelegramUser.STATUS_SVYAZAN
        tg.save()

        # Голосовые команды (Модуль H)
        golos_texty = [
            'укладка плитки 40 квадратов, штукатурка стен 120 метров',
            'демонтаж перегородок 24 квадрата, вывоз мусора 3 штуки',
            'монтаж проводки 45 точек, установка дверей 5 штук',
            'грунтовка стен 200 квадратов',
        ]
        try:
            from golos.parse import parse_pozicii
            for t in golos_texty:
                poz = parse_pozicii(t, 'srednyaya')
                GolosovayaKomanda.objects.create(brigada=brigada, tekst_raspoznanny=t, pozicii_najdeno=len(poz))
        except Exception as exc:  # noqa: BLE001
            self.stderr.write('  Голосовые демо-команды не созданы: %s' % exc)

        # Фото-акты (Модуль G) — реальные изображения с водяным знаком
        n_foto = self._demo_foto(akty)

        self.stdout.write('Addendum: чеков %d, проверок %d, подписей %d, WA %d, Telegram привязан, голос %d, фото %d'
                          % (n_chek, len(proverki_vhod), 5, 6, len(golos_texty), n_foto))

    def _demo_foto(self, akty):
        if not akty:
            return 0
        try:
            from io import BytesIO
            from PIL import Image
            from fotoakty.images import process_photo
            from fotoakty.models import FotoAkt
            from fotoakty.views import _regenerate_akt_pdf
        except Exception:  # noqa: BLE001
            return 0
        akt = akty[0]
        podpisi_foto = ['Стена до штукатурки', 'Стена после штукатурки', 'Электрощиток собран']
        cvet = [(150, 120, 90), (180, 170, 160), (90, 100, 120)]
        watermark = [akt.brigada.nazvanie, akt.adres_obekta, 'Дата: демо']
        n = 0
        for i, podpis in enumerate(podpisi_foto):
            buf = BytesIO()
            Image.new('RGB', (1400, 1050), cvet[i % len(cvet)]).save(buf, 'JPEG')
            buf.seek(0)
            try:
                content, lat, lon = process_photo(buf, watermark)
            except Exception:  # noqa: BLE001
                continue
            f = FotoAkt(dokument=akt, watermark_text=' · '.join(watermark), podpis_snizu=podpis,
                        geo_lat=57.15 + i * 0.001, geo_lon=65.53 + i * 0.001)
            f.foto_file.save(f'demo_{i+1}.jpg', content, save=True)
            n += 1
        if n:
            _regenerate_akt_pdf(akt)
        return n
