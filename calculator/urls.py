from django.urls import path

from . import views

app_name = 'calculator'

urlpatterns = [
    path('', views.raschet_list, name='list'),
    path('new/', views.create_raschet, name='create'),
    path('<int:pk>/', views.raschet_detail, name='detail'),
    path('<int:pk>/download-xlsx/', views.raschet_download_xlsx, name='download_xlsx'),
]
