from django.urls import path
from . import views

urlpatterns = [
    # path('iniciar/<int:planejamento_id>/', views.iniciar_apontamento, name='iniciar_apontamento'),
    # path('interromper/<int:apontamento_id>/', views.interromper_apontamento, name='interromper_apontamento'),
    # path('retornar/<int:apontamento_id>/', views.retornar_apontamento, name='retornar_apontamento'),
    # path('finalizar_parcial/<int:apontamento_id>/', views.finalizar_parcial_apontamento, name='finalizar_parcial_apontamento'),
    path('detalhe/<int:apontamento_id>/', views.detalhe_apontamento, name='detalhe_apontamento'),

]
