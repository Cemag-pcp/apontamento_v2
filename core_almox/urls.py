from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('solicitacoes-page/',views.page_solicitacoes, name='solicitacoes_page'),
    path('configuracoes/', views.configuracoes_sla, name='configuracoes_sla'),
    path('gerenciar-solicitantes/', views.gerenciar_funcionarios_almox, name='gerenciar_funcionarios_almox'),
    path('api/solicitacoes/', views.lista_solicitacoes, name='lista_solicitacoes'),
    path('api/atualizar-dados/', views.atualizar_dados, name='atualizar_dados'),
    path('api/processar_edicao/', views.processar_edicao, name='processar_edicao'),
]
