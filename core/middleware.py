"""
Авто-вход владельца (однопользовательский режим).

Если AUTO_LOGIN=True (по умолчанию), любой анонимный запрос автоматически
логинится под аккаунтом владельца — сайт открывается сразу в системе, без лендинга
и без страницы авторизации. Управляется переменной окружения AUTO_LOGIN в .env.

ВНИМАНИЕ: в этом режиме сайт не защищён паролем — кто угодно, открыв адрес, попадает
в кабинет владельца. Для многопользовательского режима задайте AUTO_LOGIN=False.
Раздел /admin/ авто-входом не затрагивается и требует обычной авторизации.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.utils import timezone

_EXEMPT_PREFIXES = ('/admin', '/static', '/media', '/sw.js', '/manifest', '/offline', '/sign/')


def auto_login_middleware(get_response):
    def middleware(request):
        if (getattr(settings, 'AUTO_LOGIN', False)
                and not request.user.is_authenticated
                and not any(request.path.startswith(p) for p in _EXEMPT_PREFIXES)):
            user = _ensure_owner()
            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                request.user = user
        return get_response(request)

    return middleware


def _ensure_owner():
    """Гарантирует существование аккаунта владельца с бригадой на тарифе PRO."""
    from core.models import Brigada
    User = get_user_model()
    username = getattr(settings, 'AUTO_LOGIN_USERNAME', 'vladelec')
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    try:
        user.brigada
    except Brigada.DoesNotExist:
        Brigada.objects.create(
            user=user, nazvanie='Моя бригада', telefon='+70000000000',
            tarif='pro', data_okonchaniya_tarifa=timezone.localdate() + timedelta(days=3650),
        )
    return user
