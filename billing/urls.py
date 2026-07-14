from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.plans, name='plans'),
    path('upgrade/<str:tarif>/', views.upgrade, name='upgrade'),
    path('success/', views.success, name='success'),
    path('webhook/', views.webhook, name='webhook'),
    path('history/', views.history, name='history'),
]
