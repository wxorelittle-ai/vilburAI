from django.urls import path

from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.katalog, name='katalog'),
    path('master/<int:pk>/', views.master, name='master'),

    path('birzha/', views.birzha, name='birzha'),
    path('birzha/new/', views.izlishek_create, name='izlishek_create'),
    path('birzha/<int:pk>/snyat/', views.izlishek_snyat, name='izlishek_snyat'),

    path('tendery/', views.tendery, name='tendery'),
    path('tendery/new/', views.tender_create, name='tender_create'),
    path('tendery/<int:pk>/', views.tender_detail, name='tender_detail'),
    path('tendery/<int:pk>/zakryt/', views.tender_zakryt, name='tender_zakryt'),
]
