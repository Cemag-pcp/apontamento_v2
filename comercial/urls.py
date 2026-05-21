from django.urls import path

from . import views

app_name = 'comercial'

urlpatterns = [
    path('conf-pedido/', views.conf_pedido, name='conf_pedido'),
    path('api/conf-pedido/', views.api_conf_pedido, name='api_conf_pedido'),
    path('api/conf-pedido/conferir/', views.api_marcar_conferido, name='api_marcar_conferido'),
    path('api/conf-pedido/desfazer/', views.api_desfazer_conferido, name='api_desfazer_conferido'),
    path('api/conferidos/', views.api_conferidos, name='api_conferidos'),
]
