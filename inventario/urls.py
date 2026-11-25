from django.urls import path

from . import views

app_name = 'inventario'

urlpatterns = [
    # Lista de inventários; com ?id=<id>&aba=<aba> mostra o inventário
    # escolhido ("entrar") e a aba do menu dele. Uma rota só, porque o controle
    # de acesso (RotaAccessMiddleware) compara o caminho exato com as rotas
    # cadastradas.
    path('', views.inventario_home, name='home'),
    path('api/criar/', views.criar_inventario, name='criar'),
    path('api/<int:inventario_id>/cadastros/criar/', views.criar_cadastro, name='criar_cadastro'),
    path('api/cadastros/<int:cadastro_id>/excluir/', views.excluir_cadastro, name='excluir_cadastro'),
    path('api/cadastros/<int:cadastro_id>/responsavel/', views.definir_responsavel, name='definir_responsavel'),
    path('api/<int:inventario_id>/contagem/importar/', views.importar_contagem, name='importar_contagem'),
    path('api/<int:inventario_id>/contagem/limpar/', views.limpar_contagem, name='limpar_contagem'),
    path('api/<int:inventario_id>/status/', views.alterar_status, name='alterar_status'),
    path('api/<int:inventario_id>/contagem/recontagem/', views.alterar_recontagem, name='alterar_recontagem'),

    # Link público da contagem (sem login; liberado no RotaAccessMiddleware)
    path('contagem/<uuid:token>/', views.contagem_publica, name='contagem_publica'),
    path('contagem/<uuid:token>/api/itens/', views.contagem_publica_itens, name='contagem_publica_itens'),
    path(
        'contagem/<uuid:token>/api/itens/<int:item_id>/',
        views.contagem_publica_registrar,
        name='contagem_publica_registrar',
    ),
    path(
        'contagem/<uuid:token>/api/fora-da-lista/',
        views.contagem_publica_fora_da_lista,
        name='contagem_publica_fora_da_lista',
    ),
]
