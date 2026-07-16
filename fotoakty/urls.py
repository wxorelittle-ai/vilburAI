from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'fotoakty'

urlpatterns = [
    # У остальных модулей корень раздела — рабочая страница; здесь ей быть галерее,
    # иначе закладка на /fotoakty/ отдаёт 404.
    path('', RedirectView.as_view(pattern_name='fotoakty:galereya', permanent=False)),
    path('galereya/', views.galereya, name='galereya'),
    path('document/<int:dokument_pk>/upload/', views.upload_foto, name='upload'),
    path('<int:foto_pk>/delete/', views.delete_foto, name='delete'),
]
