from django.urls import path

from . import views

app_name='serra'

urlpatterns = [
    path('', views.planejamento, name='planejamento'),

    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/ordens-criadas/<int:pk_ordem>/<str:name_maquina>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),
    path('api/get-mp/', views.get_mp, name='get_mp'),
    path('api/get-peca/', views.get_peca, name='get_peca'),
    path('api/criar-ordem/', views.criar_ordem, name='criar_ordem'),
    path('api/importar-ordens-serra/', views.importar_ordens_serra, name='importar_ordens_serra'),
    path('api/status_maquinas/', views.get_status_maquinas, name='status_maquinas'),
    path('api/ultimas_pecas_produzidas/', views.get_ultimas_pecas_produzidas, name='ultimas_pecas_produzidas'),
    path('api/status_ordem/', views.get_contagem_status_ordem, name='status_ordem'),
    path('api/buscar-maquinas-disponiveis/', views.get_maquinas_disponiveis, name='buscar_maquinas_disponiveis'),
    path('api/parar-maquina/', views.parar_maquina, name='parar_maquina'),

    path('api/apontamentos-peca/serra', views.api_apontamentos_peca, name='api_apontamentos_peca'),
    path('api/apontamentos-mp/serra', views.api_apontamentos_mp, name='api_apontamentos_mp'),

]
