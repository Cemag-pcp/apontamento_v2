from django.urls import path
from . import views

app_name = "inspecao"

urlpatterns = [
    path('api/conjuntos-inspecionados/<str:codigo>/', views.add_remove_conjuntos_inspecionados, name='remover_conjunto'),
    path('api/conjuntos-inspecionados/', views.add_remove_conjuntos_inspecionados, name='adicionar_conjunto'),

    path('api/itens-inspecao-pintura/', views.get_itens_inspecao_pintura, name='itens-inspecao-pintura'),
    path('api/itens-inspecionados-pintura/', views.get_itens_inspecionados_pintura, name='itens-inspecionados-pintura'),
    path('api/itens-reinspecao-pintura/', views.get_itens_reinspecao_pintura, name='itens-reinspecao-pintura'),
    path('api/alerta-itens-pintura/', views.alerta_itens_pintura, name='alerta-itens-pintura'),

    path('api/historico-pintura/<int:id>', views.get_historico_pintura, name='historico-pintura'),
    path('api/historico-causas-pintura/<int:id>', views.get_historico_causas_pintura, name='historico-causas-pintura'),

    path('api/envio-inspecao-pintura/', views.envio_inspecao_pintura, name='envio-inspecao-pintura'),
    path('api/envio-reinspecao-pintura/', views.envio_reinspecao_pintura, name='envio-reinspecao-pintura'),

    path('api/itens-inspecao-montagem/', views.get_itens_inspecao_montagem, name='itens-inspecao-montagem'),
    path('api/itens-inspecionados-montagem/', views.get_itens_inspecionados_montagem, name='itens-inspecionados-montagem'),
    path('api/itens-reinspecao-montagem/', views.get_itens_reinspecao_montagem, name='itens-reinspecao-montagem'),

    path('api/itens-inspecao-estamparia/', views.get_itens_inspecao_estamparia, name='itens-inspecao-estamparia'),
    path('api/itens-inspecionados-estamparia/', views.get_itens_inspecionados_estamparia, name='itens-inspecionados-estamparia'),
    path('api/itens-reinspecao-estamparia/', views.get_itens_reinspecao_estamparia, name='itens-reinspecao-estamparia'),

    path('api/envio-inspecao-estamparia/', views.inspecionar_estamparia, name='inspecionar_estamparia'),
    path('api/envio-reinspecao-estamparia/', views.envio_reinspecao_estamparia, name='envio_reinspecao_estamparia'),

    path('api/historico-estamparia/<int:id>', views.get_historico_estamparia, name='historico-estamparia'),
    path('api/historico-causas-estamparia/<int:id>', views.get_historico_causas_estamparia, name='historico-causas-estamparia'),

    path('api/motivos-causas/<str:setor>/', views.motivos_causas, name='motivos_causas'),

    path('api/historico-montagem/<int:id>', views.get_historico_montagem, name='historico-montagem'),
    path('api/historico-causas-montagem/<int:id>', views.get_historico_causas_montagem, name='historico-montagem'),

    path('api/envio-inspecao-montagem/', views.envio_inspecao_montagem, name='envio-inspecao-montagem'),
    path('api/envio-reinspecao-montagem/', views.envio_reinspecao_montagem, name='envio-reinspecao-montagem'),

    path('api/itens-reinspecao-tubos-cilindros/', views.get_itens_reinspecao_tubos_cilindros, name='itens-reinspecao-tubos-cilindros'),
    path('api/itens-inspecionados-tubos-cilindros/', views.get_itens_inspecionados_tubos_cilindros, name='itens-inspecionados-tubos-cilindros'),
    path('api/envio-inspecao-tubos-cilindros/', views.envio_inspecao_tubos_cilindros, name='envio-inspecao-tubos-cilindros'),
    path('api/envio-reinspecao-tubos-cilindros/', views.envio_reinspecao_tubos_cilindros, name='envio-reinspecao-tubos-cilindros'),

    path('api/<int:id>/historico-tubos-cilindros/', views.get_historico_tubos_cilindros, name='historico-tubos-cilindros'),
    path('api/<int:id>/historico-causas-tubos-cilindros/', views.get_historico_causas_tubos_cilindros, name='historico-causas-tubos-cilindros'),

    path('tanque/', views.inspecao_tanque, name='inspecao-tanque'),
    path('api/envio-inspecao-tanque/', views.envio_inspecao_tanque, name='envio-inspecao-tanque'),
    path('api/envio-reinspecao-tanque/', views.envio_reinspecao_tanque, name='envio-reinspecao-tanque'),

    path('api/itens-reinspecao-tanque/', views.get_itens_reinspecao_tanque, name='itens-reinspecao-tanque'),
    path('api/itens-inspecionados-tanque/', views.get_itens_inspecionados_tanque, name='itens-inspecionados-tanque'),

    path('api/<int:id>/historico-tanque/', views.get_historico_tanque, name='historico-tanque'),

    path('api/delete-execucao/', views.delete_execution, name='delete-execution'),
    path('api/delete-execucao-estanqueidade/', views.delete_execution_estanqueidade, name='delete-execution-estanqueidade')
]

# templates
urlpatterns += [
    path('montagem/', views.inspecao_montagem, name='inspecao-montagem'),
    path('conjuntos-inspecionados/', views.conjuntos_inspecionados_montagem, name='conjuntos-inspecionados-montagem'),
    path('estamparia/', views.inspecao_estamparia, name='inspecao-estamparia'),
    path('pintura/', views.inspecao_pintura, name='inspecao-pintura'),
    path('tubos-cilindros/', views.inspecao_tubos_cilindros, name='inspecao-tubos-cilindros'),
    path('dashboard/pintura/', views.dashboard_pintura, name='dasdashboard_pinturahboard'),
    path('dashboard/montagem/', views.dashboard_montagem, name='dasdashboard_montagemhboard'),
    path('dashboard/estamparia/', views.dashboard_estamparia, name='dasdashboard_estampariahboard'),
    path('dashboard/tanque/', views.dashboard_tanque, name='dashboard-tanque'),
    path('dashboard/tubos-cilindros/', views.dashboard_tubos_cilindros, name='dashboard-tubos-cilindros')
]

# dashboard
urlpatterns += [
    path('pintura/api/indicador-pintura-analise-temporal/', views.indicador_pintura_analise_temporal, name='indicador_pintura_analise_temporal'),
    path('pintura/api/indicador-pintura-resumo-analise-temporal/', views.indicador_pintura_resumo_analise_temporal, name='indicador_pintura_resumo_analise_temporal'),
    path('pintura/api/causas-nao-conformidade/', views.causas_nao_conformidade_mensal, name='causas_nao_conformidade_mensal'),
    path('pintura/api/imagens-nao-conformidade/', views.imagens_nao_conformidade_pintura, name='imagens_nao_conformidade_pintura'),
    path('pintura/api/causas-nao-conformidade-tipo/', views.causas_nao_conformidade_por_tipo, name='causas_nao_conformidade_por_tipo'),

    path('montagem/api/indicador-montagem-analise-temporal/', views.indicador_montagem_analise_temporal, name='indicador_montagem_analise_temporal'),
    path('montagem/api/indicador-montagem-resumo-analise-temporal/', views.indicador_montagem_resumo_analise_temporal, name='indicador_montagem_resumo_analise_temporal'),
    path('montagem/api/causas-nao-conformidade/', views.causas_nao_conformidade_mensal_montagem, name='causas_nao_conformidade_mensal'),
    path('montagem/api/imagens-nao-conformidade/', views.imagens_nao_conformidade_montagem, name='imagens_nao_conformidade_montagem'),

    path('estamparia/api/indicador-estamparia-analise-temporal/', views.indicador_estamparia_analise_temporal, name='indicador_estamparia_analise_temporal'),
    path('estamparia/api/indicador-estamparia-resumo-analise-temporal/', views.indicador_estamparia_resumo_analise_temporal, name='indicador_estamparia_resumo_analise_temporal'),
    path('estamparia/api/causas-nao-conformidade/', views.causas_nao_conformidade_mensal_estamparia, name='causas_nao_conformidade_mensal'),
    path('estamparia/api/imagens-nao-conformidade/', views.imagens_nao_conformidade_estamparia, name='imagens_nao_conformidade_estamparia'),
    path('estamparia/api/fichas-inspecao/', views.ficha_inspecao_estamparia, name='ficha_inspecao_estamparia'),

    path('tanque/api/indicador-tanque-analise-temporal/', views.indicador_tanque_analise_temporal, name='indicador_tanque_analise_temporal'),
    path('tanque/api/indicador-tanque-resumo-analise-temporal/', views.indicador_tanque_resumo_analise_temporal, name='indicador_tanque_resumo_analise_temporal'),
    path('tanque/api/causas-nao-conformidade/', views.causas_nao_conformidade_mensal_tanque, name='causas_nao_conformidade_mensal'),

    path('tubos-cilindros/api/indicador-tubos-cilindros-analise-temporal/', views.indicador_tubos_cilindros_analise_temporal, name='indicador_tubos_cilindros_analise_temporal'),
    path('tubos-cilindros/api/indicador-tubos-cilindros-resumo-analise-temporal/', views.indicador_tubos_cilindros_resumo_analise_temporal, name='indicador_tubos_cilindros_resumo_analise_temporal'),
    path('tubos-cilindros/api/imagens-nao-conformidade/', views.imagens_nao_conformidade_tubos_cilindros, name='imagens_nao_conformidade_tubos_cilindros'),
    path('tubos-cilindros/api/causas-nao-conformidade/', views.causas_nao_conformidade_mensal_tubos_cilindros, name='causas_nao_conformidade_mensal'),
]