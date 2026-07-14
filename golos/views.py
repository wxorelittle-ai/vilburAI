import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from .models import GolosovayaKomanda
from .parse import parse_pozicii


def golos_dostupen(brigada) -> bool:
    return brigada.effective_tarif == 'pro'


@login_required
@require_POST
def raspoznat(request):
    """Принимает распознанный в браузере текст, парсит в позиции сметы (JSON)."""
    brigada = request.user.brigada
    if not golos_dostupen(brigada):
        return JsonResponse({'ok': False, 'error': 'Голосовой ввод доступен на тарифе PRO.'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('bad json')

    text = (payload.get('text') or '').strip()
    uroven = payload.get('uroven') or 'srednyaya'
    if not text:
        return JsonResponse({'ok': False, 'error': 'Пустой текст.'})

    pozicii = parse_pozicii(text, uroven)
    GolosovayaKomanda.objects.create(
        brigada=brigada, tekst_raspoznanny=text, pozicii_najdeno=len(pozicii),
        status=GolosovayaKomanda.STATUS_OBRABOTAN,
    )
    return JsonResponse({'ok': True, 'text': text, 'pozicii': pozicii})
