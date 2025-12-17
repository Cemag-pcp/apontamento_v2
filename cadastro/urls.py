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

    # Peças
    path('cadastro-pecas/', views.cadastro_pecas, name='cadastro_pecas'),
    path('api/cadastro-pecas/', views.cadastro_pecas_api, name='cadastro_pecas_api'),

]
