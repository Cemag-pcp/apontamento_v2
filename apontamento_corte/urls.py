from django.urls import path
from . import views
from .views import ProcessarArquivoView,SalvarArquivoView

app_name = 'corte'

urlpatterns = [
    
    #templates
    path('', views.planejamento, name='planejamento'),
    path('duplicar-op/', views.duplicar_op, name='duplicar_op'),

    #apis
    path('api/salvar-arquivo/', SalvarArquivoView.as_view(), name='salvar_arquivo'),
    path('api/processar-arquivo/', ProcessarArquivoView.as_view(), name='processar_arquivo'),
    path('duplicar-op/api/ordens-criadas/', views.get_ordens_criadas_duplicar_ordem, name='get_ordens_criadas_duplicar_ordem'),
    path('duplicar-op/api/pecas/', views.get_pecas, name='get_pecas'),
    path('duplicar-op/api/duplicar-ordem/<int:pk_ordem>/pecas/', views.get_pecas_ordem_duplicar_ordem, name='get_pecas_ordem_duplicar_ordem'),
    path('duplicar-op/api/duplicar-ordem/<int:pk_ordem>/', views.gerar_op_duplicada, name='gerar_op_duplicada'),
    
    path('api/excluir-op-padrao/', views.excluir_op_padrao, name='excluir_op_padrao'),
    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/ordens-criadas/<int:pk_ordem>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),
    path('api/ordens-sequenciadas/', views.get_ordens_sequenciadas, name='get_ordens_sequenciadas'),
    path('api/resequenciar-ordem/', views.resequenciar_ordem, name='resequenciar_ordem'),
    path('api/excluir-ordem/', views.excluir_ordem, name='excluir_ordem'),
    path('api/salvar-prioridade/', views.definir_prioridade, name='definir_prioridade'),

    # verificar se esse endpoint está sendo usado
    path('api/duplicador-ordem/filtrar/', views.filtrar_ordens, name='filtrar_ordens'),

    path('api/get-pecas/', views.get_pecas, name='get_pecas'),

    # consumir dados via google sheets
    path('api/apontamentos/corte', views.api_ordens_finalizadas, name='api_ordens_finalizadas'),
    path('api/apontamentos/mp', views.api_ordens_finalizadas_mp, name='api_ordens_finalizadas_mp'),
    path('api/apontamentos/criadas', views.api_ordens_criadas, name='api_ordens_criadas'),
]

# dashboard
urlpatterns += [
    path('dashboard', views.dashboard, name='dashboard'),

    path('api/dashboard/indicador-hora-operacao-maquina', views.indicador_hora_operacao_maquina, name='indicador_hora_operacao_maquina'),
    path('api/dashboard/indicador-finalizacao-maquina', views.indicador_ordem_finalizada_maquina, name='indicador_ordem_finalizada_maquina'),
    path('api/dashboard/indicador-pecas-produzidas-maquina', views.indicador_peca_produzida_maquina, name='indicador_peca_produzida_maquina'),
]
