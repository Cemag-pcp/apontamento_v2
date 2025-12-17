from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .views import CustomLoginView
from . import api_view

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('api/excluir-ordem/', views.excluir_ordem, name='excluir_ordem'),
    path('propriedades-ordem/', views.propriedades_ordem, name='propriedades_ordem'),
    path('pecas-corte/', views.pecas_corte, name='pecas_corte'),
    path('pecas-serra/', views.pecas_serra, name='pecas_serra'),
    path('pecas-usinagem/', views.pecas_usinagem, name='pecas_usinagem'),
    path('pecas-estamparia/', views.pecas_estamparia, name='pecas_estamparia'),
    
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),  # Para logout, se necessário

    path('versao/', views.versao, name='versao'),
    
    path('acessos/', views.acessos, name='acessos'),
    path("api/usuarios/", views.api_listar_usuarios, name="listar_usuarios"),
    path("api/listar-acessos/<int:user_id>/", views.api_listar_acessos, name="listar_acessos_usuarios"),
    path("api/atualizar-acessos/<int:user_id>/update", views.api_atualizar_acessos, name="atualizar_acessos"),
    path('api/retornar-processo/', views.retornar_processo, name='retornar_processo'),

    path('api/retornar-maquina/', views.retornar_maquina, name='retornar_maquina'),
    path('api/parar-maquina/', views.parar_maquina, name='parar_maquina'),
    path('api/ultimas_pecas_produzidas/', views.get_ultimas_pecas_produzidas, name='ultimas_pecas_produzidas'),
    path('api/status_ordem/', views.get_contagem_status_ordem, name='status_ordem'),
    path('api/status_maquinas/', views.get_status_maquinas, name='status_maquinas'),
    path('api/buscar-maquinas-disponiveis/', views.get_maquinas_disponiveis, name='buscar_maquinas_disponiveis'),

    path('notificacoes/', views.notificacoes_pagina, name='notificacoes'),
    path('api/notificacoes/', views.notificacoes_api, name='api_notificacoes'),
    path('api/notificacoes/marcar-como-lidas/', views.marcar_notificacoes_como_lidas, name='api_marcar_como_lidas'),
    path('api/propriedades-ordem/', views.propriedades_ordem_api, name='propriedades_ordem_api'),
    path('api/pecas-corte/', views.pecas_corte_api, name='pecas_corte_api'),
    path('api/pecas-serra/', views.pecas_serra_api, name='pecas_serra_api'),
    path('api/pecas-usinagem/', views.pecas_usinagem_api, name='pecas_usinagem_api'),
    path('api/pecas-estamparia/', views.pecas_estamparia_api, name='pecas_estamparia_api'),

    path('api/rpa/update-transfer/', api_view.rpa_update_transfer, name='rpa_update_transfer'),
    path('api/rpa/update-status/', api_view.rpa_update_status, name='rpa_update_status'),

]

#consulta de peças
urlpatterns += [
    path('home-pecas/', views.consulta_pecas, name='consulta_pecas'),
    path('api/consulta-carreta/', views.consulta_carretas, name='consulta_carretas'),
    path('api/consulta-conjunto/', views.consulta_conjunto, name='consulta_conjunto'),
    path('api/consulta-peca/', views.mostrar_pecas_completa, name='mostrar_pecas_completa'),
]
