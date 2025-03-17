from django.urls import path

from . import views

app_name = 'montagem'

# apis
urlpatterns = [
    path('api/criar-ordem/', views.criar_ordem, name='criar_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-criadas/', views.ordens_criadas, name='ordens_criadas'),
    path('api/ordens-interrompidas/', views.ordens_interrompidas, name='ordens_interrompidas'),
    path('api/ordens-iniciadas/', views.ordens_iniciadas, name='ordens_iniciadas'),
    path('api/andamento-carga/', views.percentual_concluido_carga, name='percentual_concluido_carga'),
    path('api/listar-operadores/', views.listar_operadores, name='listar_operadores'),
    path('api/listar-motivos-interrupcao/', views.listar_motivos_interrupcao, name='listar_motivos_interrupcao'),
    path('api/verificar-qt-restante/', views.verificar_qt_restante, name='verificar_qt_restante'),
    path('api/andamento-ultimas-cargas/', views.andamento_ultimas_cargas, name='andamento_ultimas_cargas'),
    path('api/listar-pecas-disponiveis/', views.listar_pecas_disponiveis, name='listar_pecas_disponiveis'),
    path('api/buscar-maquinas/', views.buscar_maquinas, name='buscar_maquinas'),


]

# templates
urlpatterns += [
    path('', views.planejamento, name='planejamento'),
]
