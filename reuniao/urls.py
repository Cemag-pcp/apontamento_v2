from django.urls import path
from . import views

app_name = 'reuniao'

urlpatterns = [
    path('', views.reuniao_home, name='home'),
    path('api/criar-report/', views.criar_report, name='criar_report'),
    path('api/listar-reports/', views.listar_reports, name='listar_reports'),
    path(
        'api/reports/<int:report_id>/conclusao/',
        views.atualizar_conclusao_report,
        name='atualizar_conclusao_report',
    ),
    path(
        'api/reports/<int:report_id>/excluir/',
        views.excluir_report,
        name='excluir_report',
    ),
    path('api/tabela-producao/', views.tabela_producao, name='tabela_producao'),
    path('api/andamento-live/', views.andamento_live, name='andamento_live'),
]
