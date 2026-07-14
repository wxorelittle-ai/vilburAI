from django.urls import path

from . import views

app_name = 'nalogi'

urlpatterns = [
    path('', views.glavnaya, name='glavnaya'),
    path('probit/', views.probit, name='probit'),
    path('otchet/oplatit/', views.otchet_oplatit, name='oplatit'),
    path('cheki.xlsx', views.cheki_excel, name='excel'),
]
