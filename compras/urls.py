from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    path('', views.analise, name='analise'),
    path('api/material-direto/', views.api_material_direto, name='api_material_direto'),
    path('api/projecao/', views.api_projecao, name='api_projecao'),
]
