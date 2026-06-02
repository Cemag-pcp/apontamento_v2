from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    path('', views.analise, name='analise'),
    path('api/material-direto/', views.api_material_direto, name='api_material_direto'),
    path('api/projecao/', views.api_projecao, name='api_projecao'),
    path('api/dolar/', views.api_dolar, name='api_dolar'),
    path('api/analise-ia/', views.api_analise_ia, name='api_analise_ia'),

    path('mat_indireto/', views.mat_indireto, name='mat_indireto'),
    path('mat_indireto/api/debug-colunas/', views.api_debug_colunas_indireto, name='api_debug_colunas_indireto'),
    path('mat_indireto/api/material-direto/', views.api_material_indireto, name='api_material_indireto'),
    path('mat_indireto/api/projecao/', views.api_projecao_indireto, name='api_projecao_indireto'),
    path('mat_indireto/api/dolar/', views.api_dolar, name='api_dolar_indireto'),
    path('mat_indireto/api/analise-ia/', views.api_analise_ia_indireto, name='api_analise_ia_indireto'),
]
