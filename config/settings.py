"""
Django settings for Бригадир.Про

Все чувствительные параметры берутся из переменных окружения (.env).
См. .env.example — полный список переменных.
"""

from pathlib import Path
from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Безопасность -----------------------------------------------------------

SECRET_KEY = config('SECRET_KEY', default='django-insecure-CHANGE-ME-IN-PRODUCTION')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# --- Приложения ---------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Бригадир.Про — приложения по модулям ТЗ
    'core.apps.CoreConfig',            # Пользователи, Brigada (Этап 1)
    'documents.apps.DocumentsConfig',  # Модуль A — генератор документов
    'calculator.apps.CalculatorConfig',  # Модуль C — калькулятор себестоимости
    'smety.apps.SmetyConfig',          # Модуль B — генератор смет
    'billing.apps.BillingConfig',      # Тарифы, ЮKassa, LimitTracker
    'objekty.apps.ObjektyConfig',      # Модуль J — контроль объектов + AI-ассистент (Addendum №2)
    'podpis.apps.PodpisConfig',        # Модуль I — простая электронная подпись (ПЭП)
    'fotoakty.apps.FotoaktyConfig',    # Модуль G — фото-акты с геолокацией
    'nalogi.apps.NalogiConfig',        # Модуль D — налоги и чеки ФНС
    'proverka.apps.ProverkaConfig',    # Модуль E — проверка заказчика
    'messengers.apps.MessengersConfig',  # Модуль F — WhatsApp / Telegram
    'golos.apps.GolosConfig',          # Модуль H — голосовой ввод
    'marketplace.apps.MarketplaceConfig',  # Модуль 4 — маркетплейс (репутация, биржа, тендеры)
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.brigada_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- База данных ---------------------------------------------------------------
# По умолчанию — SQLite (для локальной разработки).
# В проде задаётся DATABASE_URL=postgres://user:pass@host:5432/dbname (см. .env.example)

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# --- Валидация паролей -----------------------------------------------------
# Требование ТЗ (раздел 8): 8+ символов, цифра, буква

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Локализация (ТЗ: только русский на MVP, раздел 16) -----------------------

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# --- Статика и медиа -----------------------------------------------------------

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Аутентификация -------------------------------------------------------------

LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:landing'

# --- Email (заглушка на MVP — консоль; в проде SMTP, см. .env.example) ---------

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@brigadir.pro')

# --- ЮKassa (Модуль тарифов/оплаты) ---------------------------------------------

YOOKASSA_SHOP_ID = config('YOOKASSA_SHOP_ID', default='')
YOOKASSA_SECRET_KEY = config('YOOKASSA_SECRET_KEY', default='')
YOOKASSA_TEST_MODE = config('YOOKASSA_TEST_MODE', default=True, cast=bool)

# --- AI-ассистент прораба (Модуль J, раздел 6.8 ТЗ) ----------------------------
# Без ключа модуль работает в демо-режиме (правило-основанная сводка), с ключом —
# серверный вызов Anthropic API (см. objekty/ai_assistant.py).

ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
ANTHROPIC_MODEL = config('ANTHROPIC_MODEL', default='claude-sonnet-4-6')

# --- СМС-шлюз (Модуль I — ПЭП, раздел 6 ТЗ) ------------------------------------
# Без ключа коды подписания показываются на экране (демо), с ключом — реальная СМС.
SMS_API_KEY = config('SMS_API_KEY', default='')

# --- ФНС «Мой налог» (Модуль D, раздел 6.4 ТЗ) --------------------------------
# Без ключа чеки пробиваются в демо-режиме (локально), с ключом — реальная ФНС.
FNS_API_KEY = config('FNS_API_KEY', default='')

# --- Проверка контрагентов (Модуль E, раздел 6.5 ТЗ) --------------------------
# Без ключа — демо (внутренний чёрный список + модель), с ключом — Контур/СПАРК.
KONTUR_API_KEY = config('KONTUR_API_KEY', default='')

# --- Мессенджеры (Модуль F, раздел 6.6 ТЗ) ------------------------------------
# Без ключей — демо. WhatsApp — через Wazzup; Telegram-бот — long-polling.
WHATSAPP_API_KEY = config('WHATSAPP_API_KEY', default='')
TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_BOT_USERNAME = config('TELEGRAM_BOT_USERNAME', default='brigadirpro_bot')

# --- Безопасность в проде (включается через .env при DEBUG=False) --------------

if not DEBUG:
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# --- Тарифная сетка (раздел 5 ТЗ) — используется в billing/limits.py ----------

# objekty/ai_zaprosy — Модуль J (раздел 5 ТЗ): «Старт»/«Самозанятый» — недоступен,
# «Бригадир» — до 3 объектов и 10 AI-запросов/мес, «PRO» — безлимит. None = безлимит.
TARIFF_LIMITS = {
    'start': {'dokumenty': 1, 'raschety': 3, 'smety': 0, 'objekty': 0, 'ai_zaprosy': 0, 'cheki': 0, 'proverki': 0, 'label': 'Старт', 'price': 0},
    'samozanyaty': {'dokumenty': 10, 'raschety': None, 'smety': 0, 'objekty': 0, 'ai_zaprosy': 0, 'cheki': 5, 'proverki': 0, 'label': 'Самозанятый', 'price': 490},
    'brigadir': {'dokumenty': None, 'raschety': None, 'smety': 20, 'objekty': 3, 'ai_zaprosy': 10, 'cheki': None, 'proverki': 3, 'label': 'Бригадир', 'price': 990},
    'pro': {'dokumenty': None, 'raschety': None, 'smety': None, 'objekty': None, 'ai_zaprosy': None, 'cheki': None, 'proverki': None, 'label': 'PRO', 'price': 1990},
}
