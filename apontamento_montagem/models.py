from django.db import models
from django.utils.timezone import now

from cadastro.models import Pecas,Operador
from core.models import Ordem, OrdemProcesso

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_montagem')
    peca = models.CharField(max_length=255)
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)
    operador=models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador_produzido_montagem', blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    processo_ordem = models.ForeignKey(OrdemProcesso, on_delete=models.CASCADE, related_name='processo_ordem_montagem', blank=True, null=True)
    