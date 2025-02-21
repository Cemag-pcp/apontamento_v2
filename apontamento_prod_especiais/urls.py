from django.urls import path

from . import views

app_name = 'prod_esp'

urlpatterns = [
    path('', views.planejamento, name='planejamento'),

    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/ordens-criadas/<int:pk_ordem>/<str:name_maquina>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),

    path('api/get-pecas/', views.get_pecas, name='get_pecas'),
    path('api/criar-ordem-prod-especiais/', views.planejar_ordem_prod_esp, name='planejar_ordem_prod_esp'),

]
