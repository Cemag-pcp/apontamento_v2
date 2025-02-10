from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .views import CustomLoginView

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('api/excluir-ordem/', views.excluir_ordem, name='excluir_ordem'),
    
    # path('login/', auth_views.LoginView.as_view(template_name='login/login.html'), name='login'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),  # Para logout, se necessário

    path('versao/', views.versao, name='versao'),

    path('api/retornar-maquina/', views.retornar_maquina, name='retornar_maquina'),
    path('api/parar-maquina/', views.parar_maquina, name='parar_maquina'),
    path('api/ultimas_pecas_produzidas/', views.get_ultimas_pecas_produzidas, name='ultimas_pecas_produzidas'),
    path('api/status_ordem/', views.get_contagem_status_ordem, name='status_ordem'),
    path('api/status_maquinas/', views.get_status_maquinas, name='status_maquinas'),
    path('api/buscar-maquinas-disponiveis/', views.get_maquinas_disponiveis, name='buscar_maquinas_disponiveis'),

]