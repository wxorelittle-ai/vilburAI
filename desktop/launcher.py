"""
Десктоп-лончер Вильбур AI.

Что делает:
1. Готовит .env (копирует из .env.example и генерирует SECRET_KEY при первом запуске).
2. Применяет миграции базы данных (SQLite-файл рядом с проектом, данные сохраняются
   между запусками).
3. Поднимает Django на свободном локальном порту (в фоновом потоке).
4. Открывает приложение в нативном окне через pywebview — либо, если pywebview
   недоступен на этой системе, в браузере по умолчанию.

Запускать через install_windows.bat / install_mac_linux.sh — они сами готовят
виртуальное окружение и зависимости. Повторные запуски — через run_desktop.bat/.sh.
"""

import os
import secrets
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# --- Безопасность консоли Windows -----------------------------------------------
# На части систем Windows консоль не подхватывает UTF-8 даже после chcp 65001
# в .bat-файле, и Python падает с UnicodeEncodeError на первом же print()
# с кириллицей — окно закрывается мгновенно, будто «ничего не произошло».
# Принудительно переключаем stdout/stderr в UTF-8 с заменой нечитаемых символов
# вместо падения.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

APP_TITLE = 'Вильбур AI'


def ensure_env_file():
    """Создаёт .env из .env.example при первом запуске, с уникальным SECRET_KEY."""
    env_path = BASE_DIR / '.env'
    example_path = BASE_DIR / '.env.example'
    if env_path.exists():
        return
    if not example_path.exists():
        print('Внимание: .env.example не найден, .env не создан.')
        return
    content = example_path.read_text(encoding='utf-8')
    random_key = secrets.token_urlsafe(50)
    content = content.replace(
        'SECRET_KEY=change-me-to-a-random-50-char-string',
        f'SECRET_KEY={random_key}',
    )
    env_path.write_text(content, encoding='utf-8')
    print('Создан файл .env с уникальным SECRET_KEY.')


def find_free_port(start_port=8000, attempts=20):
    port = start_port
    for _ in range(attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    raise RuntimeError('Не удалось найти свободный порт.')


def setup_django():
    ensure_env_file()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()

    from django.core.management import call_command
    print('Применяю миграции базы данных...')
    call_command('migrate', interactive=False, verbosity=1)

    # Автосоздание суперпользователя для доступа в /admin/, если его ещё нет
    from django.contrib.auth.models import User
    if not User.objects.filter(is_superuser=True).exists():
        password = secrets.token_urlsafe(9)
        User.objects.create_superuser('admin', 'admin@brigadir.local', password)
        print('=' * 60)
        print(f'Создан администратор: логин admin / пароль {password}')
        print('Он нужен только для входа в /admin/. Сохраните пароль.')
        print('=' * 60)


def run_server(port, started_event, error_holder):
    try:
        from django.core.servers.basehttp import WSGIServer, WSGIRequestHandler
        from django.core.wsgi import get_wsgi_application

        application = get_wsgi_application()
        httpd = WSGIServer(('127.0.0.1', port), WSGIRequestHandler)
        httpd.set_app(application)
        started_event.set()
        httpd.serve_forever()
    except Exception as exc:
        error_holder['error'] = exc
        started_event.set()


def main():
    setup_django()
    port = find_free_port()
    url = f'http://127.0.0.1:{port}/'

    started_event = threading.Event()
    error_holder = {}
    server_thread = threading.Thread(
        target=run_server, args=(port, started_event, error_holder), daemon=True,
    )
    server_thread.start()

    # Ждём подтверждения, что сервер реально поднялся (а не просто "спим 1 секунду").
    if not started_event.wait(timeout=15):
        raise RuntimeError('Сервер не запустился за 15 секунд — проверьте лог выше.')
    if 'error' in error_holder:
        raise error_holder['error']

    print(f'Вильбур AI запущен: {url}')

    try:
        import webview
        webview.create_window(APP_TITLE, url, width=1280, height=860, min_size=(360, 600))
        webview.start()
    except Exception as exc:
        print(f'Нативное окно недоступно ({exc}), открываю в браузере по умолчанию...')
        webbrowser.open(url)
        print('Приложение работает. Закройте это окно консоли, чтобы остановить сервер.')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print('Остановлено.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('\n' + '=' * 60)
        print('ОШИБКА ЗАПУСКА:')
        print('=' * 60)
        traceback.print_exc()
        print('=' * 60)
        print('Скопируйте текст ошибки выше, если обращаетесь за помощью.')
        input('\nНажмите Enter, чтобы закрыть окно...')
        sys.exit(1)
