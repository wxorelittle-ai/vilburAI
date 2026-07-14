from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .forms import RegistrationForm, BrigadaProfileForm


def landing(request):
    """
    Лендинг (раздел 7.2 ТЗ): 3 экрана — боль пропадающих авансов → решение → тарифы.
    Если пользователь уже вошёл — сразу в личный кабинет.
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    tarify = _tarify_dlya_shablona()
    return render(request, 'core/landing.html', {'tarify': tarify})


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
            messages.success(request, 'Добро пожаловать в Бригадир.Про! Создайте свой первый договор бесплатно.')
            return redirect('core:dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'core/register.html', {'form': form})


@login_required
def dashboard(request):
    """
    Личный кабинет (раздел 7.2 ТЗ): sidebar + карточки статистики.
    Документы и расчёты — реальные счётчики (Модули A и C). Сметы — заглушка до Модуля B.
    """
    from documents.models import Dokument
    from calculator.models import Raschet
    from smety.models import Smeta

    brigada = request.user.brigada
    context = {
        'brigada': brigada,
        'stats': {
            'dokumentov_sozdano': Dokument.objects.filter(brigada=brigada).count(),
            'raschetov_sdelano': Raschet.objects.filter(brigada=brigada).count(),
            'smet_sozdano': Smeta.objects.filter(brigada=brigada).count(),
        },
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
