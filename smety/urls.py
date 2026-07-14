from django.urls import path

from . import views

app_name = 'smety'

urlpatterns = [
    path('', views.smeta_list, name='list'),
    path('new/', views.smeta_create, name='create'),
    path('add-row/', views.add_row, name='add_row'),
    path('add-row-from-baza/', views.add_row_from_baza, name='add_row_from_baza'),
    path('<int:pk>/', views.smeta_detail, name='detail'),
    path('<int:pk>/edit/', views.smeta_edit, name='edit'),
    path('<int:pk>/download/', views.smeta_download, name='download'),
    path('<int:pk>/duplicate/', views.smeta_duplicate, name='duplicate'),
    path('<int:pk>/publish/', views.smeta_publish, name='publish'),
    path('<int:pk>/unpublish/', views.smeta_unpublish, name='unpublish'),
]
