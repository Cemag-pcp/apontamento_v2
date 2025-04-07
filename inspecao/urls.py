from django.urls import path
from . import views

app_name = "inspecao"

urlpatterns = [
    path('montagem/', views.inspecao_montagem, name='inspecao-montagem'),
    
    path('estamparia/', views.inspecao_estamparia, name='inspecao-estamparia'),

    path('pintura/', views.inspecao_pintura, name='inspecao-pintura'),
    path('api/itens-inspecao-pintura/', views.get_itens_inspecao_pintura, name='itens-inspecao-pintura'),
    path('api/itens-inspecionados-pintura/', views.get_itens_inspecionados_pintura, name='itens-inspecionados-pintura'),
    path('api/itens-reinspecao-pintura/', views.get_itens_reinspecao_pintura, name='itens-reinspecao-pintura'),

    path('api/historico-pintura/<int:id>', views.get_historico_pintura, name='historico-pintura'),
    path('api/historico-causas-pintura/<int:id>', views.get_historico_causas_pintura, name='historico-causas-pintura'),

    path('api/envio-inspecao-pintura/', views.envio_inspecao_pintura, name='envio-inspecao-pintura'),
    path('api/envio-reinspecao-pintura/', views.envio_reinspecao_pintura, name='envio-reinspecao-pintura'),

    path('api/itens-inspecao-montagem/', views.get_itens_inspecao_montagem, name='itens-inspecao-montagem'),
    path('api/itens-inspecionados-montagem/', views.get_itens_inspecionados_montagem, name='itens-inspecionados-montagem'),
    path('api/itens-reinspecao-montagem/', views.get_itens_reinspecao_montagem, name='itens-reinspecao-montagem'),

    path('api/itens-inspecao-estamparia/', views.get_itens_inspecao_estamparia, name='itens-inspecao-estamparia'),
    path('api/envio-inspecao-estamparia/', views.inspecionar_estamparia, name='inspecionar_estamparia'),

    path('api/motivos-causas/<str:setor>/', views.motivos_causas, name='motivos_causas'),

    path('api/historico-montagem/<int:id>', views.get_historico_montagem, name='historico-montagem'),
    path('api/historico-causas-montagem/<int:id>', views.get_historico_causas_montagem, name='historico-montagem'),

    path('api/envio-inspecao-montagem/', views.envio_inspecao_montagem, name='envio-inspecao-montagem'),
    path('api/envio-reinspecao-montagem/', views.envio_reinspecao_montagem, name='envio-reinspecao-montagem'),

    path('tubos-cilindros/', views.inspecao_tubos_cilindros, name='inspecao-tubos-cilindros'),
    path('api/itens-reinspecao-tubos-cilindros/', views.get_itens_reinspecao_tubos_cilindros, name='itens-reinspecao-tubos-cilindros'),
    path('api/itens-inspecionados-tubos-cilindros/', views.get_itens_inspecionados_tubos_cilindros, name='itens-inspecionados-tubos-cilindros'),
    path('api/envio-inspecao-tubos-cilindros/', views.envio_inspecao_tubos_cilindros, name='envio-inspecao-tubos-cilindros'),
    path('api/envio-reinspecao-tubos-cilindros/', views.envio_reinspecao_tubos_cilindros, name='envio-reinspecao-tubos-cilindros'),

    path('api/<int:id>/historico-tubos-cilindros/', views.get_historico_tubos_cilindros, name='historico-tubos-cilindros'),
    path('api/<int:id>/historico-causas-tubos-cilindros/', views.get_historico_causas_tubos_cilindros, name='historico-causas-tubos-cilindros'),

    path('tanque/', views.inspecao_tanque, name='inspecao-tanque'),
    path('api/envio-inspecao-tanque/', views.envio_inspecao_tanque, name='envio-inspecao-tanque'),
    path('api/envio-reinspecao-tanque/', views.envio_reinspecao_tanque, name='envio-reinspecao-tanque'),

    path('api/itens-reinspecao-tanque/', views.get_itens_reinspecao_tanque, name='itens-reinspecao-tanque'),
    path('api/itens-inspecionados-tanque/', views.get_itens_inspecionados_tanque, name='itens-inspecionados-tanque'),

    path('api/<int:id>/historico-tanque/', views.get_historico_tanque, name='historico-tanque'),
]
