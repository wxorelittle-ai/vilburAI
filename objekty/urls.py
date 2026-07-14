from django.urls import path

from . import views

app_name = 'objekty'

urlpatterns = [
    path('', views.obekty_list, name='list'),
    path('new/', views.obekt_create, name='create'),
    path('<int:pk>/', views.obekt_detail, name='detail'),
]
