from django.urls import path
from . import views

urlpatterns = [
    path('', views.criar_solicitacoes, name='criar_solicitacoes'),

    path('api/ajax/get-cc/', views.get_cc_by_matricula, name='get_cc_by_matricula'),
    path('api/ajax/get-unidade/', views.get_unidade_by_item, name='get_unidade_by_item'),
    path('api/ajax/carregar-classes/', views.carregar_classes, name='ajax_carregar_classes'),

    path('historico/requisicao', views.historico_requisicao, name='historico_requisicao'),
    path('api/historico/processa-historico-requisicao/', views.solicitacao_data_requisicao, name='solicitacao_data_requisicao'),
    
    path('historico/transferencia', views.historico_transferencia, name='historico_transferencia'),
    path('api/historico/processa-historico-transferencia/', views.solicitacao_data_transferencia, name='solicitacao_data_transferencia'),

    path('api/cadastrar-novo-item/', views.cadastro_novo_item, name='cadastro_novo_item'),
    path('api/cadastrar-nova-matricula/', views.cadastro_nova_matricula, name='cadastro_nova_matricula'),

    path('gerir-solicitacao-cadastro/', views.gerir_solicitacoes, name='gerir_solicitacoes'),
    
    path('api/cadastro-item/edit/<int:pk>/<str:tipo_cadastro>', views.edit_solicitacao_cadastro_item, name='edit_solicitacao_cadastro_item'),
    path('api/cadastro-item/edit/<int:pk>', views.edit_solicitacao_cadastro_matricula, name='edit_solicitacao_cadastro_matricula'),

    path('api/editar/<str:tipo_solicitacao>/<int:requisicao_id>/', views.edit_solicitacao, name='edit_solicitacao'),

    path('erros/', views.home_erros, name='home_erros'),
    path('api/erros/data-transferencia/', views.data_erros_transferencia, name='data_erros_transferencia'),
    path('api/erros/data-requisicao/', views.data_erros_requisicao, name='data_erros_requisicao'),

    path('api/get-dados/', views.get_data_solicitacao, name='get_data_solicitacao'),
    path('api/get-recursos/', views.get_recursos, name='get_recursos'),

    path('api/receber-edicao/', views.receber_edicao, name='receber_edicao'),
    path('api/receber-ajuste-manual/', views.receber_ajuste_manual, name='receber_edicao'),


    # teste
    path('api/receber-form-edit/', views.receberFormEdit, name='receberFormEdit'),

]


