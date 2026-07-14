"""
Обработка фотографий для фото-актов (Модуль G, Addendum №1 ТЗ):
- поворот по EXIF-ориентации;
- извлечение геолокации из EXIF (GPS) → десятичные градусы;
- сжатие до 1200×900;
- водяной знак: дата, адрес объекта, бригада (шрифт DejaVu — корректная кириллица).
"""

import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont, ExifTags

MAX_SIZE = (1200, 900)
_FONT_PATH = os.path.join(str(settings.BASE_DIR), 'static', 'fonts', 'DejaVuSans.ttf')

_ORIENTATION_TAG = next((k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None)
_GPS_TAG = next((k for k, v in ExifTags.TAGS.items() if v == 'GPSInfo'), None)


def _load_font(size):
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _apply_orientation(img):
    try:
        exif = img._getexif()
        if exif and _ORIENTATION_TAG in exif:
            o = exif[_ORIENTATION_TAG]
            if o == 3:
                img = img.rotate(180, expand=True)
            elif o == 6:
                img = img.rotate(270, expand=True)
            elif o == 8:
                img = img.rotate(90, expand=True)
    except Exception:  # noqa: BLE001
        pass
    return img


def _dms_to_deg(dms, ref):
    try:
        d, m, s = (float(x) for x in dms)
        deg = d + m / 60 + s / 3600
        if ref in ('S', 'W'):
            deg = -deg
        return round(deg, 6)
    except Exception:  # noqa: BLE001
        return None


def extract_gps(img):
    """Возвращает (lat, lon) или (None, None)."""
    try:
        exif = img._getexif()
        if not exif or _GPS_TAG not in exif:
            return None, None
        gps = exif[_GPS_TAG]
        names = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps.items()}
        lat = _dms_to_deg(names.get('GPSLatitude'), names.get('GPSLatitudeRef'))
        lon = _dms_to_deg(names.get('GPSLongitude'), names.get('GPSLongitudeRef'))
        return lat, lon
    except Exception:  # noqa: BLE001
        return None, None


def process_photo(uploaded_file, watermark_lines):
    """Возвращает (ContentFile jpeg, lat, lon)."""
    img = Image.open(uploaded_file)
    lat, lon = extract_gps(img)
    img = _apply_orientation(img)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail(MAX_SIZE, Image.LANCZOS)

    draw = ImageDraw.Draw(img, 'RGBA')
    font = _load_font(max(14, img.width // 45))
    lines = [ln for ln in watermark_lines if ln]
    line_h = font.size + 6
    pad = 10
    box_h = line_h * len(lines) + pad
    # полупрозрачная подложка снизу
    draw.rectangle([0, img.height - box_h, img.width, img.height], fill=(38, 36, 33, 160))
    y = img.height - box_h + pad // 2
    for ln in lines:
        draw.text((pad, y), ln, font=font, fill=(255, 255, 255, 235))
        y += line_h

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85, optimize=True)
    return ContentFile(buf.getvalue()), lat, lon
