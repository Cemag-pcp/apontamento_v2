from django.urls import path

from . import views

app_name='serra'

urlpatterns = [
    path('', views.planejamento, name='planejamento'),
    path('historico/', views.historico, name='historico'),

    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/ordens-criadas/<int:pk_ordem>/<str:name_maquina>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),
    path('api/get-mp/', views.get_mp, name='get_mp'),
    path('api/get-peca/', views.get_peca, name='get_peca'),
    path('api/criar-ordem/', views.criar_ordem, name='criar_ordem'),
    path('api/importar-ordens-serra/', views.importar_ordens_serra, name='importar_ordens_serra'),
    path('api/verificar-dados-ordem/', views.verificar_mp_pecas_na_ordem, name='verificar_ordem'),
    path('api/duplicar-ordem/', views.duplicar_ordem, name='duplicar_ordem'),
    path('api/excluir-peca-ordem/', views.excluir_peca_ordem, name='excluir_peca_ordem'),

    path('atualizar-propriedades/', views.atualizar_propriedades_ordem, name='atualizar_propriedades_ordem'),
    path('atualizar-pecas/', views.atualizar_pecas_ordem, name='atualizar_pecas_ordem'),

    path('api/apontamentos-peca/serra', views.api_apontamentos_peca, name='api_apontamentos_peca'),
    path('api/apontamentos-mp/serra', views.api_apontamentos_mp, name='api_apontamentos_mp'),

]

# dashboard
urlpatterns += [
    path('dashboard', views.dashboard, name='dashboard'),

    path('api/dashboard/indicador-hora-operacao-maquina', views.indicador_hora_operacao_maquina, name='indicador_hora_operacao_maquina'),
    path('api/dashboard/indicador-finalizacao-maquina', views.indicador_ordem_finalizada_maquina, name='indicador_ordem_finalizada_maquina'),
    path('api/dashboard/indicador-pecas-produzidas-maquina', views.indicador_peca_produzida_maquina, name='indicador_peca_produzida_maquina'),
]