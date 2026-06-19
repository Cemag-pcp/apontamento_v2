# urls.py
from django.urls import path
from .views import crud
from . import views

app_name = 'cadastro'

urlpatterns = [
    path('crud/', crud, name='crud'),

    # Máquinas
    path('api/buscar-maquinas/', views.buscar_maquinas, name='buscar_maquinas'),

    # Processos
    path('api/buscar-processos/', views.buscar_processos, name='buscar_processos'),
    
    # Setores
    path('api/setores/', views.api_setores, name='api_setores'),
    
    # Operadores
    path('operadores/',views.operadores, name='operadores'),
    path('api/operadores/',views.api_operadores, name='api_operadores'),
    path('add/operador/',views.add_operador, name='add_operador'),
    path('edit/operador/<int:pk>/',views.edit_operador, name='edit_operador'),

    # Máquinas
    path('maquinas/', views.maquinas, name='maquinas'),
    path('api/maquinas/', views.api_maquinas, name='api_maquinas'),

    # Peças
    path('cadastro-pecas/', views.cadastro_pecas, name='cadastro_pecas'),
    path('api/cadastro-pecas/', views.cadastro_pecas_api, name='cadastro_pecas_api'),

    # Conjuntos
    path('cadastro-conjuntos/', views.cadastro_conjuntos, name='cadastro_conjuntos'),
    path('api/cadastro-conjuntos/', views.cadastro_conjuntos_api, name='cadastro_conjuntos_api'),
    path('cadastro-itens-explodidos/', views.cadastro_itens_explodidos, name='cadastro_itens_explodidos'),

    # Carretas Explodidas
    path('carretas-explodidas/', views.cadastro_carretas_explodidas, name='cadastro_carretas_explodidas'),
    path('api/carretas-explodidas/', views.cadastro_carretas_explodidas_api, name='cadastro_carretas_explodidas_api'),

    # Chapas de corte
    path('chapas-corte/', views.chapas_corte, name='chapas_corte'),
    path('api/chapas-corte/', views.chapas_corte_api, name='chapas_corte_api'),

]
