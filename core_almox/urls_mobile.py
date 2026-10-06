from django.urls import path

from . import api_mobile

app_name = 'almox_mobile'

urlpatterns = [
    path('solicitacoes/', api_mobile.SolicitacoesPendentesView.as_view(), name='solicitacoes'),
    path('operadores/', api_mobile.OperadoresView.as_view(), name='operadores'),
    path('solicitacoes/<str:tipo>/<int:solicitacao_id>/entregar/', api_mobile.EntregarSolicitacaoView.as_view(), name='entregar'),
]
