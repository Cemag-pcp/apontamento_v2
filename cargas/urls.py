from django.urls import path

from . import views

app_name = 'cargas'

urlpatterns = [
    path('', views.home, name='home'),
    path('historico/', views.historico_cargas, name='historico_cargas'),

    path('api/buscar-carretas-base/', views.buscar_dados_carreta_planilha, name="buscar_dados_carreta_planilha"),
    path('api/gerar-arquivos/', views.gerar_arquivos_sequenciamento, name="gerar_arquivos_sequenciamento"),
    path('api/gerar-dados-ordem/', views.gerar_dados_sequenciamento, name="gerar_dados_sequenciamento"),
    path('api/andamento-cargas/', views.andamento_cargas, name="andamento_cargas"),
    path('api/remanejar-carga/', views.remanejar_carga, name="remanejar_carga"),
    path('api/atualizar-planejamento/', views.atualizar_ordem_existente, name="atualizar_ordem_existente"),
    path('api/historico-planejamento-montagem/', views.historico_ordens_montagem, name="historico_ordens_montagem"),
    path('api/historico-planejamento-solda/', views.historico_ordens_solda, name="historico_ordens_solda"),
    path('api/editar-planejamento/', views.editar_planejamento, name="editar_planejamento"),
    path('api/historico-planejamento-pintura/', views.historico_ordens_pintura, name="historico_ordens_pintura"),
    path('api/excluir-planejamento/', views.excluir_ordens_dia_setor, name="excluir_ordens_dia_setor"),
    path('api/imprimir-etiquetas/', views.enviar_etiqueta_impressora, name="enviar_etiqueta_impressora"),
    path('api/imprimir-etiquetas-unitaria/', views.enviar_etiqueta_unitaria_impressora, name="enviar_etiqueta_unitaria_impressora"),
    path('api/imprimir-etiquetas-pintura/', views.enviar_etiqueta_impressora_pintura, name="enviar_etiqueta_impressora_pintura"),

    # google sheets
    path('api/ordens_em_andamento_finalizada_pintura/', views.ordens_em_andamento_finalizada_pintura, name="ordens_em_andamento_finalizada_pintura"),
    path('api/verificar_cargas_geradas/', views.verificar_cargas_geradas, name="verificar_cargas_geradas"),
    path('api/ordens_em_andamento_finalizada_montagem/', views.ordens_status_montagem, name="ordens_status_montagem"),
    path('api/ordens_em_andamento_finalizada_solda/', views.ordens_status_solda, name="ordens_status_solda"),
    path('api/pecas_status_retrabalho_pintura/', views.pecas_status_retrabalho_pintura, name="pecas_status_retrabalho_pintura"),
    path('api/ordens_finalizadas_pintura_inicio_ano/', views.ordens_finalizadas_pintura_inicio_ano, name="ordens_finalizadas_pintura_inicio_ano"),

]
