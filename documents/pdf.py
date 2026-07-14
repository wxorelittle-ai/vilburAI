import os
import tempfile
from io import BytesIO

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa

# --- Windows-фикс шрифтов xhtml2pdf ------------------------------------------
# xhtml2pdf пишет @font-face шрифт во временный NamedTemporaryFile и отдаёт его
# путь reportlab, не закрыв дескриптор. На Windows файл заблокирован эксклюзивно,
# и reportlab падает с PermissionError. Патчим: создаём temp с delete=False и
# сразу закрываем, чтобы reportlab мог его открыть. Иначе PDF не генерируются.
import xhtml2pdf.files as _x2pdf_files  # noqa: E402


def _safe_get_named_tmp_file(self):
    data = self.get_data()
    tmp = tempfile.NamedTemporaryFile(suffix=getattr(self, 'suffix', ''), delete=False)
    try:
        if data:
            tmp.write(data)
            tmp.flush()
    finally:
        tmp.close()
    if getattr(self, 'path', None) is None:
        self.path = tmp.name
    _x2pdf_files.files_tmp.append(tmp)
    return tmp


if not getattr(_x2pdf_files.BaseFile, '_brigadir_win_fontfix', False):
    _x2pdf_files.BaseFile.get_named_tmp_file = _safe_get_named_tmp_file
    _x2pdf_files.BaseFile._brigadir_win_fontfix = True


def _link_callback(uri, rel):
    """
    Резолвит относительные /static/ и /media/ ссылки в абсолютные файловые пути,
    как того требует xhtml2pdf для встраивания логотипа и шрифтов в PDF.
    """
    if uri.startswith(settings.STATIC_URL):
        rel_path = uri.replace(settings.STATIC_URL, '')
        for candidate_root in [settings.STATIC_ROOT, *settings.STATICFILES_DIRS]:
            candidate = os.path.join(str(candidate_root), rel_path)
            if os.path.isfile(candidate):
                return candidate
        return uri
    if uri.startswith(settings.MEDIA_URL):
        rel_path = uri.replace(settings.MEDIA_URL, '')
        candidate = os.path.join(str(settings.MEDIA_ROOT), rel_path)
        if os.path.isfile(candidate):
            return candidate
        return uri
    return uri


def render_pdf(template_path: str, context: dict) -> bytes:
    """Рендерит Django-шаблон в PDF (bytes). Возвращает None при ошибке рендера."""
    html = render_to_string(template_path, context)
    buffer = BytesIO()
    pdf = pisa.pisaDocument(
        BytesIO(html.encode('UTF-8')),
        dest=buffer,
        encoding='UTF-8',
        link_callback=_link_callback,
    )
    if pdf.err:
        return None
    return buffer.getvalue()
