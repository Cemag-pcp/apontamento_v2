from django.urls import path

from . import views

app_name = 'estamparia'

urlpatterns = [
    path('', views.planejamento, name='planejamento'),
    path('historico/', views.historico, name='historico'),
    path('erp/apontamentos/', views.erp_apontamentos_estamparia, name='erp_apontamentos_estamparia'),

    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/painel-prioridades/', views.get_painel_prioridades, name='get_painel_prioridades'),
    path('api/painel-prioridades/retirar/', views.retirar_ordem_prioridade, name='retirar_ordem_prioridade'),
    path('api/ordens-criadas/<int:pk_ordem>/<str:name_maquina>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),
    path('api/ordens-ag-prox-proc/', views.get_ordens_ag_prox_proc, name='get_ordens_ag_prox_proc'),
    
    path('api/get-pecas/', views.get_pecas, name='get_pecas'),
    path('api/criar-ordem-estamparia/', views.planejar_ordem_estamparia, name='planejar_ordem_estamparia'),
    
    path('atualizar-pecas/', views.atualizar_pecas_ordem, name='atualizar_pecas_ordem'),

    path('api/apontamentos-peca/estamparia', views.api_apontamentos_peca, name='api_apontamentos_peca'),
    path('api/erp/apontamentos/', views.api_erp_apontamentos_estamparia, name='api_erp_apontamentos_estamparia'),
    path('api/erp/apontamentos/<int:pk>/apontar/', views.api_erp_apontar_item_estamparia, name='api_erp_apontar_item_estamparia'),
    path('api/retornar-processo/', views.retornar_processo, name='retornar_processo')
]

# Google sheets
urlpatterns += [
    path('api/ordem-finalizadas', views.api_ordens_finalizadas, name='api_ordens_finalizadas'),
]

# dashboard
urlpatterns += [
    path('dashboard', views.dashboard, name='dashboard'),

    path('api/dashboard/indicador-hora-operacao-maquina', views.indicador_hora_operacao_maquina, name='indicador_hora_operacao_maquina'),
    path('api/dashboard/indicador-finalizacao-maquina', views.indicador_ordem_finalizada_maquina, name='indicador_ordem_finalizada_maquina'),
    path('api/dashboard/indicador-pecas-produzidas-maquina', views.indicador_peca_produzida_maquina, name='indicador_peca_produzida_maquina'),
    path('api/dashboard/kpis-consolidado', views.dashboard_kpis_consolidado, name='dashboard_kpis_consolidado'),
    path('api/dashboard/producao-inspecao', views.dashboard_producao_inspecao, name='dashboard_producao_inspecao'),
]
