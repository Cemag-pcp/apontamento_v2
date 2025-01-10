from django.db import models
from django.utils.timezone import now

from core.models import Ordem

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_corte')
    peca=models.CharField(max_length=255)
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)


