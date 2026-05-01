from django.urls import path
from . import views

urlpatterns = [
    path('upload-document/', views.upload_document, name='upload_document'),
    path('send-email/',      views.send_email,       name='send_email'),
    path('schedule-post/',   views.schedule_post,    name='schedule_post'),
    path('export-notion/',   views.export_notion,    name='export_notion'),
    path('send-telegram/',   views.send_telegram,    name='send_telegram'),
    path('regenerate-logo/',    views.regenerate_logo,    name='regenerate_logo'),
    path('generate-prototype/', views.generate_prototype, name='generate_prototype'),
]
