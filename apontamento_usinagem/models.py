from django.db import models
from django.utils.timezone import now
from django.conf import settings

from cadastro.models import Pecas,Operador
from core.models import Ordem

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_usinagem')
    peca=models.ForeignKey(Pecas, on_delete=models.CASCADE, related_name='pecas_ordem_usinagem')
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)
    operador=models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador_produzido', blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    data_apontamento = models.DateTimeField(null=True, blank=True)
    resp_apontamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apontamentos_usinagem_responsavel',
    )
    chave_apontamento = models.TextField(null=True, blank=True)
    apontado = models.BooleanField(default=False)
    tipo_apontamento = models.CharField(max_length=20, null=True, blank=True) # manual ou api
    erro_apontamento = models.TextField(null=True, blank=True)
