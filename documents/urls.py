from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('new/', views.choose_type, name='choose_type'),
    path('new/<str:tip>/', views.create_document, name='create'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/download/', views.document_download, name='download'),
    path('<int:pk>/download-docx/', views.document_download_docx, name='download_docx'),
]
