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
    path('api/editar-planejamento/', views.editar_planejamento, name="editar_planejamento"),
    path('api/historico-planejamento-pintura/', views.historico_ordens_pintura, name="historico_ordens_pintura"),

]
