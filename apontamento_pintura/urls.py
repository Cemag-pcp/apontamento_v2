from django.urls import path

from . import views

app_name = 'pintura'

# apis
urlpatterns = [
    path('api/criar-ordem/', views.criar_ordem, name='criar_ordem'),
    path('api/add-pecas-cambao/', views.adicionar_pecas_cambao, name='adicionar_pecas_cambao'),
    path('api/finalizar-cambao/', views.finalizar_cambao, name='finalizar_cambao'),
    path('api/ordens-criadas/', views.ordens_criadas, name='ordens_criadas'),
    path('api/cambao-livre/', views.cambao_livre, name='cambao_livre'),
    path('api/cambao-processo/', views.cambao_em_processo, name='cambao_em_processo'),
    path('api/listar-operadores/', views.listar_operadores, name='listar_operadores'),
    path('api/cores-carga/', views.listar_cores_carga, name='listar_cores_carga'),
    path('api/andamento-carga/', views.percentual_concluido_carga, name='percentual_concluido_carga'),
    path('api/andamento-ultimas-cargas/', views.andamento_ultimas_cargas, name='andamento_ultimas_cargas'),
    path('ap/retrabalho-pintura/', views.retrabalho_pintura, name='retrabalho_pintura')
]

# templates
urlpatterns += [
    path('', views.planejamento, name='planejamento'),
]
