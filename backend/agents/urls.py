from django.urls import path
from . import views

urlpatterns = [
    path('upload-document/', views.upload_document, name='upload_document'),
]
