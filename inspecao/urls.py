from django.urls import path
from . import views

urlpatterns = [
    path('montagem/', views.inspecao_montagem, name='inspecao-montagem'),
    path('estamparia/', views.inspecao_estamparia, name='inspecao-estamparia'),
    path('pintura/', views.inspecao_pintura, name='inspecao-pintura'),
]