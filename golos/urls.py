from django.urls import path

from . import views

app_name = 'golos'

urlpatterns = [
    path('raspoznat/', views.raspoznat, name='raspoznat'),
]
