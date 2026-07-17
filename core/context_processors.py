from django.urls import reverse


def brigada_context(request):
    """Даёт шаблонам доступ к текущей бригаде без повторного запроса в каждом view."""
    brigada = None
    if request.user.is_authenticated:
        brigada = getattr(request.user, 'brigada', None)
    return {'current_brigada': brigada}


# Разделы навигации — один список на всё приложение. Раньше перечень ссылок был записан
# дважды: в боковом меню дашборда (14 пунктов) и в шапке (6) — они уже разъехались.
# Теперь его берут и шапка, и выдвижное меню телефона, и боковое меню дашборда.
RAZDELY = [
    ('core:dashboard', 'Кабинет', 'rabota'),
    ('documents:list', 'Документы', 'rabota'),
    ('calculator:list', 'Калькулятор', 'rabota'),
    ('smety:list', 'Сметы', 'rabota'),
    ('objekty:list', 'Объекты', 'rabota'),
    ('objekty:postavki', 'Поставки', 'rabota'),
    ('fotoakty:galereya', 'Фотофиксация', 'rabota'),
    ('nalogi:glavnaya', 'Налоги и чеки', 'rabota'),
    ('proverka:glavnaya', 'Проверка заказчика', 'rabota'),
    ('messengers:nastroiki', 'Мессенджеры', 'rabota'),
    ('marketplace:katalog', 'Каталог бригад', 'rynok'),
    ('marketplace:birzha', 'Биржа излишков', 'rynok'),
    ('marketplace:tendery', 'Тендеры', 'rynok'),
    ('billing:plans', 'Тарифы', 'akkaunt'),
    ('core:profile', 'Профиль', 'akkaunt'),
]


def menyu(request):
    """Разделы для шаблонов.

    Анонимному меню не нужно: единственные страницы без входа — публичная смета и
    подписание, и обе не должны звать заказчика в кабинет владельца.
    """
    if not request.user.is_authenticated:
        return {}
    return {'menyu_razdely': [(reverse(imya), nazvanie, gruppa)
                              for imya, nazvanie, gruppa in RAZDELY]}
