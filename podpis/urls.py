from django.urls import path

from . import views

app_name = 'podpis'

urlpatterns = [
    path('podpis/document/<int:dokument_pk>/', views.zaprosit_podpis, name='zaprosit'),
    path('sign/<slug:token>/', views.sign_page, name='sign'),
]
