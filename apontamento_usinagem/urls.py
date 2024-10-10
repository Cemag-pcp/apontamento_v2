from django.urls import path

from . import views
from apontamento.views import *

app_name='apontamento_usinagem'

urlpatterns = [
    path('iniciar/<int:planejamento_id>/', iniciar_apontamento, name='iniciar_apontamento'),
    path('finalizar/<int:planejamento_id>/', views.finalizar_apontamento, name='finalizar_apontamento'),
    path('interromper/<int:planejamento_id>/', interromper_apontamento, name='interromper_apontamento'),
    path('retornar/<int:planejamento_id>/', retornar_apontamento, name='retornar_apontamento'),
    path('finalizar_parcial/<int:planejamento_id>/', finalizar_parcial_apontamento, name='finalizar_parcial_apontamento'),
    path('editar_planejamento/<int:planejamento_id>/', views.editar_planejamento, name='editar_planejamento'),

    path('lista_ordens/', views.lista_ordens, name='lista_ordens'),
    path('planejar/', views.planejar, name='planejar'),

    path('carregar-ordens-planejadas/', views.carregar_ordens_planejadas, name='carregar_ordens_planejadas'),
    path('carregar-ordens-em-processo/', views.carregar_ordens_em_processo, name='carregar_ordens_em_processo'),
    path('carregar-ordens-interrompidas/', views.carregar_ordens_interrompidas, name='carregar_ordens_interrompidas'),

]
