from django.urls import path

from . import views

app_name = 'pintura'

# apis
urlpatterns = [
    path('api/criar-ordem/', views.criar_ordem, name='criar_ordem'),
    path('api/add-pecas-cambao/', views.adicionar_pecas_cambao, name='adicionar_pecas_cambao'),
    path('api/add-pecas-programacao/', views.adicionar_pecas_programacao, name='adicionar_pecas_programacao'),
    path('api/finalizar-cambao/', views.finalizar_cambao, name='finalizar_cambao'),
    path('api/interromper-cambao/', views.interromper_cambao, name='interromper_cambao'),
    path('api/retornar-cambao/', views.retornar_cambao, name='retornar_cambao'),
    path('api/ordens-criadas/', views.ordens_criadas, name='ordens_criadas'),
    path('api/cambao-livre/', views.cambao_livre, name='cambao_livre'),
    path('api/cambao-processo/', views.cambao_em_processo, name='cambao_em_processo'),
    path('api/listar-operadores/', views.listar_operadores, name='listar_operadores'),
    path('api/cores-carga/', views.listar_cores_carga, name='listar_cores_carga'),
    path('api/andamento-carga/', views.percentual_concluido_carga, name='percentual_concluido_carga'),
    path('api/andamento-ultimas-cargas/', views.andamento_ultimas_cargas, name='andamento_ultimas_cargas'),
    path('api/criar-ordem-fora-sequenciamento/', views.criar_ordem_fora_sequenciamento, name='criar_ordem_fora_sequenciamento'),
    path('api/listar-conjuntos/', views.listar_conjuntos, name='listar_conjuntos'),
    path('api/listar-programas/', views.listar_programas, name='listar_programas'),
    path('api/iniciar-programa/', views.iniciar_programa, name='iniciar_programa'),
    path('api/deletar-programa/', views.deletar_programa, name='deletar_programa'),

    path('api/itens-retrabalho-pintura/', views.get_itens_retrabalho_pintura, name='itens_retrabalho_pintura'),
    path('api/itens-em-processo-pintura/', views.get_itens_em_processo_pintura, name='itens_em_processo_pintura'),
    path('api/itens-retrabalhados-pintura/', views.get_itens_retrabalhados_pintura, name='itens_retrabalhados_pintura'),

    path('api/confirmar-retrabalho-pintura/', views.confirmar_retrabalho_pintura, name='confirmar_retrabalho_pintura'),
    path('api/finalizar-retrabalho-pintura/', views.finalizar_retrabalho_pintura, name='finalizar_retrabalho_pintura'),
]

# templates
urlpatterns += [
    path('', views.planejamento, name='planejamento'),
    path('programar-producao/', views.programar_producao, name='programar_producao'),
    path('retrabalho', views.retrabalho_pintura, name='retrabalho_pintura')

]

# Google sheets
urlpatterns += [
    path('api/ordem-finalizadas', views.api_ordens_finalizadas, name='api_ordens_finalizadas'),
    path('api/tempos', views.api_tempos, name='api_tempos'),
]

