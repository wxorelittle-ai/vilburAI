from django.urls import path

from . import views

app_name = 'messengers'

urlpatterns = [
    path('', views.nastroiki, name='nastroiki'),
    path('wa/<int:dokument_pk>/', views.otpravit_wa, name='otpravit_wa'),
]
