from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .forms import RegistrationForm, BrigadaProfileForm


def landing(request):
    """
    Корень сайта. Лендинг убран — сразу ведём в систему (личный кабинет).
    При AUTO_LOGIN анонимный пользователь уже авторизован middleware'ом,
    иначе dashboard сам отправит на страницу входа.
    """
    return redirect('core:dashboard')


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def register(request):
    """Регистрация новой бригады: создаёт User + Brigada, сразу логинит."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Добро пожаловать в Вильбур AI! Создайте свой первый договор бесплатно.')
            return redirect('core:dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'core/register.html', {'form': form})


@login_required
def dashboard(request):
    """
    Личный кабинет (раздел 7.2 ТЗ): секции «Что горит» / «Объекты» / «Финансы»
    вместо голых счётчиков — чтобы с порога было видно, что требует действия.
    """
    from documents.models import Dokument
    from calculator.models import Raschet
    from smety.models import Smeta
    from objekty import limits as objekty_limits
    from . import dashboard as dash

    brigada = request.user.brigada
    # объекты тянем один раз с prefetch — их читают и лента дел, и финансы, и календарь
    objekty = list(dash._objekty_brigady(brigada)) if objekty_limits.objekty_dostupny(brigada) else []

    # календарь листается: ?god=2026&mesyats=8. Мусор в параметрах — просто текущий месяц.
    try:
        god = int(request.GET.get('god', 0)) or None
        mesyats = int(request.GET.get('mesyats', 0)) or None
        if mesyats is not None and not 1 <= mesyats <= 12:
            god = mesyats = None
        if god is not None and not 2000 <= god <= 2100:
            god = mesyats = None
    except (TypeError, ValueError):
        god = mesyats = None

    context = {
        'brigada': brigada,
        'stats': {
            'dokumentov_sozdano': Dokument.objects.filter(brigada=brigada).count(),
            'raschetov_sdelano': Raschet.objects.filter(brigada=brigada).count(),
            'smet_sozdano': Smeta.objects.filter(brigada=brigada).count(),
        },
        'objekty_dostupny': bool(objekty) or objekty_limits.objekty_dostupny(brigada),
        'objekty': objekty[:6],
        'dela': dash.blizhayshie_dela(brigada, objekty=objekty)[:12] if objekty else [],
        'finansy': dash.finansy(brigada, objekty=objekty) if objekty else None,
        'kalendar': dash.kalendar_mesyaca(brigada, god, mesyats, objekty=objekty) if objekty else None,
        'dni_nedeli': dash.DNI_NEDELI,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def profile(request):
    """Редактирование профиля бригады."""
    brigada = request.user.brigada
    if request.method == 'POST':
        form = BrigadaProfileForm(request.POST, request.FILES, instance=brigada)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлён.')
            return redirect('core:profile')
    else:
        form = BrigadaProfileForm(instance=brigada)

    return render(request, 'core/profile.html', {'form': form, 'brigada': brigada})


def _tarify_dlya_shablona():
    """Данные тарифной сетки (раздел 5 ТЗ) для отображения на лендинге."""
    return [
        {
            'kod': 'start', 'nazvanie': 'Старт', 'cena': '0 ₽',
            'opisanie': '1 договор с водяным знаком, 3 расчёта калькулятора',
            'akcent': False,
        },
        {
            'kod': 'samozanyaty', 'nazvanie': 'Самозанятый', 'cena': '490 ₽/мес',
            'opisanie': '10 документов/мес, налоговый модуль (5 чеков), калькулятор безлимит',
            'akcent': False,
        },
        {
            'kod': 'brigadir', 'nazvanie': 'Бригадир', 'cena': '990 ₽/мес',
            'opisanie': 'Безлимит документов, WhatsApp/Telegram, ПЭП, контроль объектов (до 3)',
            'akcent': True,
        },
        {
            'kod': 'pro', 'nazvanie': 'PRO', 'cena': '1990 ₽/мес',
            'opisanie': 'Всё безлимит + голосовой ввод + AI-ассистент прораба',
            'akcent': False,
        },
    ]
