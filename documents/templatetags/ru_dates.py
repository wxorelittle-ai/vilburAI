from django import template

register = template.Library()

_MESYATSY_RODITELNY = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря',
}


@register.filter
def data_ru(value):
    """
    Дата в родительном падеже по-русски: «11 июля 2026», без зависимости от
    системной локали (Django-фильтр date:"F Y" даёт именительный падеж —
    «Июль» вместо грамматически верного «июля»).
    """
    if not value:
        return ''
    return f'{value.day} {_MESYATSY_RODITELNY[value.month]} {value.year}'
