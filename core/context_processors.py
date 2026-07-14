def brigada_context(request):
    """Даёт шаблонам доступ к текущей бригаде без повторного запроса в каждом view."""
    brigada = None
    if request.user.is_authenticated:
        brigada = getattr(request.user, 'brigada', None)
    return {'current_brigada': brigada}
