# urls.py
from django.urls import path
from .views import crud
from . import views

app_name = 'cadastro'

urlpatterns = [
    path('crud/', crud, name='crud'),

    path('api/buscar-maquinas/', views.buscar_maquinas, name='buscar_maquinas'),
    path('api/buscar-processos/', views.buscar_processos, name='buscar_processos'),

]
