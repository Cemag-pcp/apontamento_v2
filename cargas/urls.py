from django.urls import path

from . import views

app_name = 'cargas'

urlpatterns = [
    path('', views.home, name='home'),

    path('api/buscar-carretas-base/', views.buscar_dados_carreta_planilha, name="buscar_dados_carreta_planilha"),
    path('api/gerar-arquivos/', views.gerar_arquivos_sequenciamento, name="gerar_arquivos_sequenciamento"),
    path('api/gerar-dados-ordem/', views.gerar_dados_sequenciamento, name="gerar_dados_sequenciamento"),
    path('api/andamento-cargas/', views.andamento_cargas, name="andamento_cargas"),
    path('api/remanejar-carga/', views.remanejar_carga, name="remanejar_carga"),

]
