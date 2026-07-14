"""
AI-ассистент прораба (Addendum №2, раздел 6.8 ТЗ).

Django-вью собирает структурированный JSON-контекст ОДНОГО объекта (жёсткая
фильтрация по objekt_id — требование безопасности раздела 8/16 ТЗ: запрет утечки
данных одного объекта в контекст вопроса по другому), добавляет системный промпт
и вопрос пользователя и отправляет серверным вызовом в Anthropic API.

Без ключа ANTHROPIC_API_KEY в .env работает демо-режим: правило-основанная сводка
в том же формате (блок «⚠ Требует внимания» первым) — по аналогии с демо-режимом
ЮKassa. Ассистент ТОЛЬКО читает контекст и формирует рекомендации; никаких
операций с деньгами/статусами он не выполняет (раздел 16 ТЗ).
"""

import json

import requests
from django.conf import settings

SYSTEM_PROMPT = (
    "Ты — AI-ассистент прораба в сервисе «Бригадир.Про». Ты анализируешь контроль "
    "строительного объекта: график работ, материалы, оплату монтажникам, расходы и "
    "движение денег от заказчика. Отвечай по-русски, кратко и по делу.\n\n"
    "ФОРМАТ ОТВЕТА строго такой:\n"
    "1. Сначала блок «⚠ Требует внимания» — красные флаги (просроченные материалы, "
    "кассовый разрыв, риск переплаты монтажнику, отставание от графика). Если флагов "
    "нет — напиши «Критичных проблем нет».\n"
    "2. Затем краткий разбор по вопросу пользователя, при необходимости — таблицей.\n"
    "3. Конкретные рекомендации к действию.\n\n"
    "ВАЖНО: ты только читаешь контекст и советуешь. Ты не можешь менять деньги, "
    "статусы или объёмы — все такие операции пользователь делает сам через интерфейс "
    "с подтверждением. Считай крайнюю дату заказа материала от даты НАЧАЛА этапа."
)


def is_configured() -> bool:
    return bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))


def build_context(objekt) -> dict:
    """Собирает JSON-контекст одного объекта (только его данные)."""
    return {
        'objekt': {
            'nazvanie': objekt.nazvanie,
            'adres': objekt.adres,
            'zakazchik': objekt.zakazchik,
            'master': objekt.master_otvetstvenny,
            'status': objekt.get_status_display(),
            'data_nachala': objekt.data_nachala.isoformat(),
            'data_okonchania_plan': objekt.data_okonchania_plan.isoformat(),
            'summa_dogovora': str(objekt.summa_dogovora),
            'procent_gotovnosti': objekt.procent_gotovnosti,
            'garantiynoe_uderzhanie_procent': objekt.garantiynoe_uderzhanie_procent,
        },
        'itogi': {
            'prihod_poluchen': str(objekt.prihod_poluchen),
            'prihod_ozhidaetsya': str(objekt.prihod_ozhidaetsya),
            'rashod_itogo': str(objekt.rashod_itogo),
            'kassovy_razryv': str(objekt.kassovy_razryv),
        },
        'krasnye_flagi': objekt.krasnye_flagi,
        'zhyoltye_flagi': objekt.zhyoltye_flagi,
        'etapy': [
            {
                'nazvanie': e.nazvanie, 'edinica': e.edinica,
                'plan_objem': str(e.plan_objem), 'fact_objem': str(e.fact_objem),
                'procent': e.procent, 'temp': e.status_temp_label,
                'plan_nachalo': e.plan_data_nachala.isoformat(),
                'plan_okonchanie': e.plan_data_okonchania.isoformat(),
                'perezakryt': e.perezakryt,
            }
            for e in objekt.etapy.all()
        ],
        'materialy': [
            {
                'nazvanie': m.nazvanie, 'etap': m.etap.nazvanie,
                'status': m.status_display_effective,
                'data_zakaza_kraynyaya': m.data_zakaza_kraynyaya.isoformat() if m.data_zakaza_kraynyaya else None,
                'prosrocheno': m.prosrocheno,
            }
            for m in objekt.materialy.all()
        ],
        'oplaty_montajnikov': [
            {
                'montajnik': o.montajnik_fio, 'mesyats': o.mesyats.isoformat(),
                'plan_objem': str(o.plan_objem_mesyats), 'fact_objem': str(o.fact_objem_mesyats),
                'summa_k_oplate': str(o.summa_k_oplate), 'oplacheno': str(o.summa_oplacheno),
                'prevyshenie_grafika': o.prevyshenie_grafika,
                'oplata_sverh_podtverzhdena': o.oplacheno_sverh_grafika,
            }
            for o in objekt.oplaty_montajnikov.all()
        ],
        'dvizhenie_deneg': [
            {
                'osnovanie': d.osnovanie, 'summa': str(d.summa_nachislenie),
                'za_vychetom_garantii': str(d.summa_za_vychetom_garantii),
                'data_plan': d.data_plan.isoformat(), 'status': d.get_status_display(),
            }
            for d in objekt.dvizhenie_deneg.all()
        ],
    }


def ask(objekt, vopros: str):
    """Возвращает (otvet: str, demo: bool)."""
    context = build_context(objekt)
    if not is_configured():
        return _demo_answer(context, vopros), True
    try:
        return _anthropic_answer(context, vopros), False
    except Exception as exc:  # noqa: BLE001 — сеть/ключ могут отвалиться, не роняем UI
        return (
            f'Не удалось обратиться к AI-ассистенту ({exc}). '
            f'Ниже — автоматическая сводка:\n\n' + _demo_answer(context, vopros),
            True,
        )


def _anthropic_answer(context: dict, vopros: str) -> str:
    model = getattr(settings, 'ANTHROPIC_MODEL', 'claude-sonnet-4-6')
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': settings.ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': model,
            'max_tokens': 1500,
            'system': SYSTEM_PROMPT,
            'messages': [{
                'role': 'user',
                'content': (
                    f'Контекст объекта (JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n'
                    f'Вопрос прораба: {vopros}'
                ),
            }],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return ''.join(block.get('text', '') for block in data.get('content', [])) or 'Пустой ответ модели.'


def _demo_answer(context: dict, vopros: str) -> str:
    """Правило-основанная сводка без внешнего API — тот же формат, что у модели."""
    flagi = context['krasnye_flagi']
    zhyoltye = context.get('zhyoltye_flagi') or []
    lines = ['**⚠ Требует внимания**']
    if flagi:
        lines += [f'- {f}' for f in flagi]
    else:
        lines.append('- Критичных проблем нет.')
    if zhyoltye:
        lines += [f'- (жёлтый) {f}' for f in zhyoltye]

    o = context['objekt']
    it = context['itogi']
    lines += [
        '',
        f'**Объект «{o["nazvanie"]}»** — готовность {o["procent_gotovnosti"]}%, статус: {o["status"]}.',
        '',
        '**Деньги:**',
        f'- Получено от заказчика: {it["prihod_poluchen"]} ₽',
        f'- Ожидается: {it["prihod_ozhidaetsya"]} ₽',
        f'- Расход: {it["rashod_itogo"]} ₽',
        f'- Баланс (кассовый разрыв, если минус): {it["kassovy_razryv"]} ₽',
    ]

    etapy = context['etapy']
    if etapy:
        lines += ['', '**График работ:**']
        for e in etapy:
            lines.append(f'- {e["nazvanie"]}: {e["procent"]}% ({e["temp"]})')

    lines += [
        '',
        '**Рекомендации:**',
        '- Закажите материалы с ближайшей крайней датой в первую очередь.',
        '- Не оплачивайте монтажникам сверх планового объёма без подтверждения.',
        '- Держите приход от заказчика впереди расхода, чтобы не уйти в кассовый разрыв.',
        '',
        '_Демо-режим: ответ сформирован локально без обращения к Anthropic API. '
        'Добавьте `ANTHROPIC_API_KEY` в `.env` для полноценного AI-ассистента._',
    ]
    return '\n'.join(lines)
