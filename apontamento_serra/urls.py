from django.urls import path

from . import views
from apontamento.views import *

app_name = 'apontamento_serra'

urlpatterns = [
    path('iniciar/<int:planejamento_id>/', iniciar_apontamento, name='iniciar_apontamento'),
    path('finalizar/<int:apontamento_id>/', views.finalizar_apontamento, name='finalizar_apontamento'),
    path('interromper/<int:apontamento_id>/', interromper_apontamento, name='interromper_apontamento'),
    path('retornar/<int:apontamento_id>/', retornar_apontamento, name='retornar_apontamento'),
    path('finalizar_parcial/<int:apontamento_id>/', finalizar_parcial_apontamento, name='finalizar_parcial_apontamento'),
    path('editar_planejamento/<int:planejamento_id>/', views.editar_planejamento, name='editar_planejamento'),

    path('lista_ordens/', views.lista_ordens, name='lista_ordens'),
    path('planejar/', views.planejar, name='planejar'),

]
