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
    path('api/alterar-stage/<int:id>/', views.alterar_stage, name='alterar_stage'),
    path('api/confirmar-pacote/<int:id>/', views.confirmar_pacote, name='confirmar_pacote'),
    path('api/pacotes/mover-item/', views.mover_item, name='mover_item'),
    path('api/impressao/', views.impressao_pacote, name='impressao_pacote'),
    path('api/salvar-foto/', views.salvar_foto, name='salvar_foto'),
    path('api/buscar-fotos/<int:pacote_id>/', views.buscar_fotos, name='buscar_fotos'),
    path('api/pendencias/<int:carregamento_id>/', views.mostrar_pendencias, name='mostrar_pendencias'),
    path('api/verificar-pendencias/<int:carregamento_id>/', views.verificar_pendencias, name='verificar_pendencias'),

]
