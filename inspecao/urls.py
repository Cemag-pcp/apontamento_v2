from django.urls import path
from . import views

app_name = "inspecao"

urlpatterns = [
    path('montagem/', views.inspecao_montagem, name='inspecao-montagem'),
    path('estamparia/', views.inspecao_estamparia, name='inspecao-estamparia'),
    path('pintura/', views.inspecao_pintura, name='inspecao-pintura'),

    path('tanque/', views.inspecao_tanque, name='inspecao-tanque'),
    path('tubos-cilindros/', views.inspecao_tubos_cilindros, name='inspecao-tubos-cilindros'),
]