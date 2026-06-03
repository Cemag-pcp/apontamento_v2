from django.urls import path
from . import views

app_name = 'reuniao'

urlpatterns = [
    path('', views.reuniao_home, name='home'),
    path('api/criar-report/', views.criar_report, name='criar_report'),
    path('api/listar-reports/', views.listar_reports, name='listar_reports'),
    path('api/tabela-producao/', views.tabela_producao, name='tabela_producao'),
    path('api/andamento-live/', views.andamento_live, name='andamento_live'),
]
