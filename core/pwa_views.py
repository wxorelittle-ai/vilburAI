"""
PWA-инфраструктура (раздел 7.5 ТЗ): manifest и service worker отдаются с корня
сайта, чтобы у SW была область видимости «/» (Service-Worker-Allowed), а не /static/.
"""

from django.shortcuts import render
from django.views.decorators.cache import cache_control


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
