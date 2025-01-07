from django.db import models
from django.utils.timezone import now

from cadastro.models import Conjuntos
from core.models import Ordem

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_prod_especiais')
    conjunto=models.ForeignKey(Conjuntos, on_delete=models.CASCADE, related_name='pecas_ordem_prod_especiais')
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)

