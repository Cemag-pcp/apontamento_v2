from django.urls import path
from . import views

app_name = 'expedicao'

urlpatterns = [
    
    #templates
    path('', views.planejamento, name='planejamento'),

    #apis
    path('api/cargas_disponiveis/', views.cargas, name='cargas'),
    path('api/carretas_disponiveis/', views.carretas, name='carretas'),
    path('api/clientes_disponiveis/', views.clientes, name='clientes'),
    path('api/criar-caixa/', views.criar_caixa, name='criar_caixa'),
    path('api/buscar-cargas/', views.buscar_cargas, name='buscar_cargas'),
    path('api/guardar-pacote/', views.guardar_pacotes, name='guardar_pacotes'),
    path('api/buscar-pacote/<int:id>/', views.buscar_pacotes_carga, name='buscar_pacotes_carga'),

]
