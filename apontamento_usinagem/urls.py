from django.urls import path

from . import views

app_name = 'usinagem'

urlpatterns = [
    path('', views.planejamento, name='planejamento'),
    path('processos/', views.processos, name='processos'),

    path('api/ordens-criadas/', views.get_ordens_criadas, name='get_ordens_criadas'),
    path('api/ordens-criadas/<int:pk_ordem>/pecas/', views.get_pecas_ordem, name='get_pecas_ordem'),
    path('api/ordens/atualizar-status/', views.atualizar_status_ordem, name='atualizar_status_ordem'),
    path('api/ordens-iniciadas/', views.get_ordens_iniciadas, name='get_ordens_iniciadas'),
    path('api/ordens-interrompidas/', views.get_ordens_interrompidas, name='get_ordens_interrompidas'),
    path('api/ordens-ag-prox-proc/', views.get_ordens_ag_prox_proc, name='get_ordens_ag_prox_proc'),
    path('api/buscar-processos/', views.buscar_processos, name='buscar_processos'),
    
    path('api/get-pecas/', views.get_pecas, name='get_pecas'),
    path('api/criar-ordem-usinagem/', views.planejar_ordem_usinagem, name='planejar_ordem_usinagem'),

    path('api/apontamentos-peca/usinagem', views.api_apontamentos_peca, name='api_apontamentos_peca'),

]
