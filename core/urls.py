from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='core/login.html'),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
]
