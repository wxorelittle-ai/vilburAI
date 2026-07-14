from django.urls import path

from . import views

app_name = 'proverka'

urlpatterns = [
    path('', views.glavnaya, name='glavnaya'),
    path('<int:pk>/', views.detail, name='detail'),
]
