from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User

from core.models import Ordem

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_corte')
    peca=models.CharField(max_length=255)
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    apontamento = models.BooleanField(null=True, blank=True)
    obs_apontamento = models.CharField(max_length=255, null=True, blank=True)
    apontado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pecasordem_apontadas')
    apontado_em = models.DateTimeField(null=True, blank=True)

    # unique constraint de peça e ordem, para evitar duplicidade
    class Meta:
        unique_together = ('ordem', 'peca')

