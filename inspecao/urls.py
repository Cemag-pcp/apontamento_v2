from django.urls import path
from . import views_general
from .views import (
    corte,
    estamparia,
    estanqueidade,
    montagem,
    pintura,
    serra_usinagem,
    verificacao_funcional,
)

app_name = "inspecao"

urlpatterns = [
    path('api/conjuntos-inspecionados/<str:codigo>/', montagem.add_remove_conjuntos_inspecionados, name='remover_conjunto'),
    path('api/conjuntos-inspecionados/', montagem.add_remove_conjuntos_inspecionados, name='adicionar_conjunto'),

    path('api/itens-inspecao-pintura/', pintura.get_itens_inspecao_pintura, name='itens-inspecao-pintura'),
    path('api/itens-inspecionados-pintura/', pintura.get_itens_inspecionados_pintura, name='itens-inspecionados-pintura'),
    path('api/itens-reinspecao-pintura/', pintura.get_itens_reinspecao_pintura, name='itens-reinspecao-pintura'),
    path('api/alerta-itens-pintura/', pintura.alerta_itens_pintura, name='alerta-itens-pintura'),

    path('api/historico-pintura/<int:id>', pintura.get_historico_pintura, name='historico-pintura'),
    path('api/historico-causas-pintura/<int:id>', pintura.get_historico_causas_pintura, name='historico-causas-pintura'),
    path('api/imagens-causas-conformidades-pintura/<int:id>/<int:num_execucao>', pintura.get_imagens_causas_conformidades_pintura, name='historico-causas-pintura'),

    path('api/envio-inspecao-pintura/', pintura.envio_inspecao_pintura, name='envio-inspecao-pintura'),
    path('api/envio-reinspecao-pintura/', pintura.envio_reinspecao_pintura, name='envio-reinspecao-pintura'),

    path('api/itens-inspecao-montagem/', montagem.get_itens_inspecao_montagem, name='itens-inspecao-montagem'),
    path('api/itens-inspecionados-montagem/', montagem.get_itens_inspecionados_montagem, name='itens-inspecionados-montagem'),
    path('api/itens-reinspecao-montagem/', montagem.get_itens_reinspecao_montagem, name='itens-reinspecao-montagem'),

    path('api/itens-inspecao-estamparia/', estamparia.get_itens_inspecao_estamparia, name='itens-inspecao-estamparia'),
    path('api/itens-inspecionados-estamparia/', estamparia.get_itens_inspecionados_estamparia, name='itens-inspecionados-estamparia'),
    path('api/itens-reinspecao-estamparia/', estamparia.get_itens_reinspecao_estamparia, name='itens-reinspecao-estamparia'),

    path('api/envio-inspecao-estamparia/', estamparia.inspecionar_estamparia, name='inspecionar_estamparia'),
    path('api/envio-reinspecao-estamparia/', estamparia.envio_reinspecao_estamparia, name='envio_reinspecao_estamparia'),

    path('api/historico-estamparia/<int:id>', estamparia.get_historico_estamparia, name='historico-estamparia'),
    path('api/historico-causas-estamparia/<int:id>', estamparia.get_historico_causas_estamparia, name='historico-causas-estamparia'),

    path('api/itens-inspecao-serra-usinagem/', serra_usinagem.get_itens_inspecao_serra_usinagem, name='itens-inspecao-serra-usinagem'),
    path('api/itens-inspecionados-serra-usinagem/', serra_usinagem.get_itens_inspecionados_serra_usinagem, name='itens-inspecionados-serra-usinagem'),
    path('api/itens-reinspecao-serra-usinagem/', serra_usinagem.get_itens_reinspecao_serra_usinagem, name='itens-reinspecao-estamserra-usinagemparia'),
    path('api/get-execucao-inspecao-serra-usinagem/', serra_usinagem.get_execucao_inspecao_serra_usinagem, name='execucao-inspecao-serra-usinagem'),
    
    path('api/itens-inspecao-corte/', corte.get_itens_inspecao_corte, name='itens-inspecao-corte'),
    path('api/itens-inspecionados-corte/', corte.get_itens_inspecionados_corte, name='itens-inspecionados-corte'),
    path('api/ordem-corte/<int:ordem_id>/', corte.get_ordem_corte, name='ordem-corte'),
    path('api/detalhes-inspecao-corte/<int:peca_id>/', corte.get_detalhes_inspecao_corte, name='detalhes-inspecao-corte'),
    path('api/envio-inspecao-corte/', corte.envio_inspecao_corte, name='envio-inspecao-corte'),

    path('api/envio-inspecao-serra-usinagem/', serra_usinagem.envio_inspecao_serra_usinagem, name='inspecionar-serra-usinagem'),
    path('api/envio-reinspecao-serra-usinagem/', serra_usinagem.envio_reinspecao_serra_usinagem, name='envio-reinspecao-serra-usinagem'),

    path('api/historico-serra-usinagem/<int:id>', serra_usinagem.get_historico_serra_usinagem, name='historico-serra-usinagem'),
    path('api/historico-causas-serra-usinagem/<int:id>', serra_usinagem.get_historico_causas_serra_usinagem, name='historico-causas-serra-usinagem'),

    path('api/motivos-causas/<str:setor>/', views_general.motivos_causas, name='motivos_causas'),

    path('api/historico-montagem/<int:id>', montagem.get_historico_montagem, name='historico-montagem'),
    path('api/historico-causas-montagem/<int:id>', montagem.get_historico_causas_montagem, name='historico-montagem'),

    path('api/envio-inspecao-montagem/', montagem.envio_inspecao_montagem, name='envio-inspecao-montagem'),
    path('api/envio-reinspecao-montagem/', montagem.envio_reinspecao_montagem, name='envio-reinspecao-montagem'),

    path('api/itens-reinspecao-tubos-cilindros/', estanqueidade.get_itens_reinspecao_tubos_cilindros, name='itens-reinspecao-tubos-cilindros'),
    path('api/itens-inspecionados-tubos-cilindros/', estanqueidade.get_itens_inspecionados_tubos_cilindros, name='itens-inspecionados-tubos-cilindros'),
    path('api/envio-inspecao-tubos-cilindros/', estanqueidade.envio_inspecao_tubos_cilindros, name='envio-inspecao-tubos-cilindros'),
    path('api/envio-reinspecao-tubos-cilindros/', estanqueidade.envio_reinspecao_tubos_cilindros, name='envio-reinspecao-tubos-cilindros'),

    path('api/<int:id>/historico-tubos-cilindros/', estanqueidade.get_historico_tubos_cilindros, name='historico-tubos-cilindros'),
    path('api/<int:id>/historico-causas-tubos-cilindros/', estanqueidade.get_historico_causas_tubos_cilindros, name='historico-causas-tubos-cilindros'),

    path('tanque/', estanqueidade.inspecao_tanque, name='inspecao-tanque'),
    path('api/envio-inspecao-tanque/', estanqueidade.envio_inspecao_tanque, name='envio-inspecao-tanque'),
    path('api/envio-inspecao-solda-tanque/', estanqueidade.envio_inspecao_solda_tanque, name='envio-inspecao-solda-tanque'),
    path('api/envio-reinspecao-tanque/', estanqueidade.envio_reinspecao_tanque, name='envio-reinspecao-tanque'),

    path('api/itens-reinspecao-tanque/', estanqueidade.get_itens_reinspecao_tanque, name='itens-reinspecao-tanque'),
    path('api/itens-enviados-tanque/<int:tanque_id>/', estanqueidade.itens_enviados_tanque, name='itens-enviados-tanque'),
    path('api/itens-inspecionados-tanque/', estanqueidade.get_itens_inspecionados_tanque, name='itens-inspecionados-tanque'),

    path('api/<int:id>/historico-tanque/', estanqueidade.get_historico_tanque, name='historico-tanque'),

    path('api/delete-execucao/', views_general.delete_execution, name='delete-execution'),
    path('api/delete-execucao-estanqueidade/', views_general.delete_execution_estanqueidade, name='delete-execution-estanqueidade'),

    path('api/testes-funcionais-pintura/',verificacao_funcional.api_testes_funcionais_pintura, name='testes-funcionais-pintura'),
    path('api/realizar-verificacao-funcional/', verificacao_funcional.realizar_verificacao_funcional, name='realizar-verificacao-funcional'),
    path('api/detalhes-verificacao-funcional/<int:id>/', verificacao_funcional.detalhes_verificacao_funcional, name='detalhes-verificacao-funcional'),

]

# templates
urlpatterns += [
    path('montagem/', montagem.inspecao_montagem, name='inspecao-montagem'),
    path('conjuntos-inspecionados/', montagem.conjuntos_inspecionados_montagem, name='conjuntos-inspecionados-montagem'),
    path('serra-usinagem/', serra_usinagem.inspecao_serra_usinagem, name='inspecao-serra-usinagem'),
    path('corte/', corte.inspecao_corte, name='inspecao-corte'),
    path('estamparia/', estamparia.inspecao_estamparia, name='inspecao-estamparia'),
    path('pintura/', pintura.inspecao_pintura, name='inspecao-pintura'),
    path('verificacao-funcional-pintura/', verificacao_funcional.verificacao_funcional_pintura, name='verificacao-funcional-pintura'),
    path('tubos-cilindros/', estanqueidade.inspecao_tubos_cilindros, name='inspecao-tubos-cilindros'),
    path('dashboard/pintura/', pintura.dashboard_pintura, name='dasdashboard_pinturahboard'),
    path('dashboard/montagem/', montagem.dashboard_montagem, name='dasdashboard_montagemhboard'),
    path('dashboard/estamparia/', estamparia.dashboard_estamparia, name='dasdashboard_estampariahboard'),
    path('dashboard/serra/', serra_usinagem.dashboard_serra, name='dasdashboard_serraboard'),
    path('dashboard/usinagem/', serra_usinagem.dashboard_usinagem, name='dasdashboard_usinagemboard'),
    path('dashboard/tanque/', estanqueidade.dashboard_tanque, name='dashboard-tanque'),
    path('dashboard/tubos-cilindros/', estanqueidade.dashboard_tubos_cilindros, name='dashboard-tubos-cilindros'),
]

# dashboard
urlpatterns += [
    path('pintura/api/indicador-pintura-analise-temporal/', pintura.indicador_pintura_analise_temporal, name='indicador_pintura_analise_temporal'),
    path('pintura/api/indicador-pintura-resumo-analise-temporal/', pintura.indicador_pintura_resumo_analise_temporal, name='indicador_pintura_resumo_analise_temporal'),
    path('pintura/api/causas-nao-conformidade/', pintura.causas_nao_conformidade_mensal, name='causas_nao_conformidade_mensal'),
    path('pintura/api/imagens-nao-conformidade/', pintura.imagens_nao_conformidade_pintura, name='imagens_nao_conformidade_pintura'),
    path('pintura/api/causas-nao-conformidade-tipo/', pintura.causas_nao_conformidade_por_tipo, name='causas_nao_conformidade_por_tipo'),

    path('montagem/api/indicador-montagem-analise-temporal/', montagem.indicador_montagem_analise_temporal, name='indicador_montagem_analise_temporal'),
    path('montagem/api/indicador-montagem-resumo-analise-temporal/', montagem.indicador_montagem_resumo_analise_temporal, name='indicador_montagem_resumo_analise_temporal'),
    path('montagem/api/causas-nao-conformidade/', montagem.causas_nao_conformidade_mensal_montagem, name='causas_nao_conformidade_mensal'),
    path('montagem/api/imagens-nao-conformidade/', montagem.imagens_nao_conformidade_montagem, name='imagens_nao_conformidade_montagem'),

    path('estamparia/api/indicador-estamparia-analise-temporal/', estamparia.indicador_estamparia_analise_temporal, name='indicador_estamparia_analise_temporal'),
    path('estamparia/api/indicador-estamparia-resumo-analise-temporal/', estamparia.indicador_estamparia_resumo_analise_temporal, name='indicador_estamparia_resumo_analise_temporal'),
    path('estamparia/api/causas-nao-conformidade/', estamparia.causas_nao_conformidade_mensal_estamparia, name='causas_nao_conformidade_mensal'),
    path('estamparia/api/imagens-nao-conformidade/', estamparia.imagens_nao_conformidade_estamparia, name='imagens_nao_conformidade_estamparia'),
    path('estamparia/api/fichas-inspecao/', estamparia.ficha_inspecao_estamparia, name='ficha_inspecao_estamparia'),

    path('serra/api/indicador-serra-analise-temporal/', serra_usinagem.indicador_serra_analise_temporal, name='indicador_serra_analise_temporal'),
    path('serra/api/indicador-serra-resumo-analise-temporal/', serra_usinagem.indicador_serra_resumo_analise_temporal, name='indicador_serra_resumo_analise_temporal'),
    path('serra/api/causas-nao-conformidade/', serra_usinagem.causas_nao_conformidade_mensal_serra, name='causas_nao_conformidade_mensal_serra'),
    path('serra/api/imagens-nao-conformidade/', serra_usinagem.imagens_nao_conformidade_serra, name='imagens_nao_conformidade_serra'),
    path('serra/api/fichas-inspecao/', serra_usinagem.ficha_inspecao_serra, name='ficha_inspecao_serra'),

    path('usinagem/api/indicador-usinagem-analise-temporal/', serra_usinagem.indicador_usinagem_analise_temporal, name='indicador_usinagem_analise_temporal'),
    path('usinagem/api/indicador-usinagem-resumo-analise-temporal/', serra_usinagem.indicador_usinagem_resumo_analise_temporal, name='indicador_usinagem_resumo_analise_temporal'),
    path('usinagem/api/causas-nao-conformidade/', serra_usinagem.causas_nao_conformidade_mensal_usinagem, name='causas_nao_conformidade_mensal_usinagem'),
    path('usinagem/api/imagens-nao-conformidade/', serra_usinagem.imagens_nao_conformidade_usinagem, name='imagens_nao_conformidade_usinagem'),
    path('usinagem/api/fichas-inspecao/', serra_usinagem.ficha_inspecao_usinagem, name='ficha_inspecao_usinagem'),

    path('tanque/api/indicador-tanque-analise-temporal/', estanqueidade.indicador_tanque_analise_temporal, name='indicador_tanque_analise_temporal'),
    path('tanque/api/indicador-tanque-resumo-analise-temporal/', estanqueidade.indicador_tanque_resumo_analise_temporal, name='indicador_tanque_resumo_analise_temporal'),
    path('tanque/api/causas-nao-conformidade/', estanqueidade.causas_nao_conformidade_mensal_tanque, name='causas_nao_conformidade_mensal'),

    path('tubos-cilindros/api/indicador-tubos-cilindros-analise-temporal/', estanqueidade.indicador_tubos_cilindros_analise_temporal, name='indicador_tubos_cilindros_analise_temporal'),
    path('tubos-cilindros/api/indicador-tubos-cilindros-resumo-analise-temporal/', estanqueidade.indicador_tubos_cilindros_resumo_analise_temporal, name='indicador_tubos_cilindros_resumo_analise_temporal'),
    path('tubos-cilindros/api/imagens-nao-conformidade/', estanqueidade.imagens_nao_conformidade_tubos_cilindros, name='imagens_nao_conformidade_tubos_cilindros'),
    path('tubos-cilindros/api/causas-nao-conformidade/', estanqueidade.causas_nao_conformidade_mensal_tubos_cilindros, name='causas_nao_conformidade_mensal'),
]
