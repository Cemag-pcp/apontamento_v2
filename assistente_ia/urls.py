from django.urls import path

from . import views

app_name = 'assistente_ia'

urlpatterns = [
    path('api/chat/', views.chat, name='chat'),
    path('api/historico/', views.historico, name='historico'),
]
