from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from smety.views import public_smeta
from core import pwa_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # PWA (раздел 7.5 ТЗ) — с корня, чтобы SW видел весь сайт
    path('sw.js', pwa_views.service_worker, name='sw'),
    path('manifest.webmanifest', pwa_views.manifest, name='manifest'),
    path('offline/', pwa_views.offline, name='offline'),
    path('', include('core.urls')),
    path('documents/', include('documents.urls')),
    path('calculator/', include('calculator.urls')),
    path('smety/', include('smety.urls')),
    path('objekty/', include('objekty.urls')),
    path('billing/', include('billing.urls')),
    path('fotoakty/', include('fotoakty.urls')),
    path('nalogi/', include('nalogi.urls')),
    path('proverka/', include('proverka.urls')),
    path('messengers/', include('messengers.urls')),
    path('', include('podpis.urls')),  # /sign/<token>/ (публично) и /podpis/document/<pk>/
    path('s/<slug:slug>/', public_smeta, name='public_smeta'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
