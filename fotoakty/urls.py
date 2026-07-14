from django.urls import path

from . import views

app_name = 'fotoakty'

urlpatterns = [
    path('galereya/', views.galereya, name='galereya'),
    path('document/<int:dokument_pk>/upload/', views.upload_foto, name='upload'),
    path('<int:foto_pk>/delete/', views.delete_foto, name='delete'),
]
