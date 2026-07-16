"""
PWA-инфраструктура (раздел 7.5 ТЗ): manifest и service worker отдаются с корня
сайта, чтобы у SW была область видимости «/» (Service-Worker-Allowed), а не /static/.
"""

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control


@cache_control(max_age=0, no_store=True)
def healthz(request):
    """
    Проверка живости для мониторинга: 200 — приложение и БД в порядке, 503 — нет.
    Одного «сайт отвечает» мало: gunicorn может отвечать, пока БД недоступна.
    Эндпоинт исключён из авто-входа, чтобы пинги не плодили сессии.
    """
    try:
        with connection.cursor() as c:
            c.execute('SELECT 1')
            c.fetchone()
    except Exception as exc:  # noqa: BLE001 — любой сбой БД = сервис нездоров
        return JsonResponse({'status': 'error', 'db': str(exc)[:200]}, status=503)
    return JsonResponse({'status': 'ok', 'db': 'ok'})


@cache_control(max_age=0)
def manifest(request):
    return render(request, 'pwa/manifest.webmanifest', content_type='application/manifest+json')


@cache_control(max_age=0)
def service_worker(request):
    response = render(request, 'pwa/sw.js', content_type='application/javascript')
    # Разрешаем SW управлять всем origin, а не только каталогом, из которого отдан
    response['Service-Worker-Allowed'] = '/'
    return response


def offline(request):
    return render(request, 'pwa/offline.html')
