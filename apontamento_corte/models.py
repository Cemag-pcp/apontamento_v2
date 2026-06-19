from django.db import models
from django.utils.timezone import now
from django.conf import settings

from core.models import Ordem

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_corte')
    peca=models.CharField(max_length=255)
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    data_apontamento = models.DateTimeField(null=True, blank=True)
    resp_apontamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apontamentos_corte_responsavel',
    )
    chave_apontamento = models.TextField(null=True, blank=True)
    apontado = models.BooleanField(default=False)
    tipo_apontamento = models.CharField(max_length=20, null=True, blank=True)
    erro_apontamento = models.TextField(null=True, blank=True)

    # unique constraint de peça e ordem, para evitar duplicidade
    class Meta:
        unique_together = ('ordem', 'peca')


class TransferenciaChapaCorte(models.Model):
    STATUS_CHOICES = (
        ('pendente', 'Pendente'),
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
        ('ignorada', 'Ignorada'),
    )

    ordem = models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='transferencias_chapa_corte')
    descricao_chapa = models.CharField(max_length=255, blank=True, null=True)
    espessura_planilha = models.CharField(max_length=80, blank=True, null=True)
    espessura_mm = models.CharField(max_length=20, blank=True, null=True)
    codigo_chapa = models.CharField(max_length=20, blank=True, null=True)
    quantidade_chapas = models.FloatField(default=0)
    peso_total = models.FloatField(default=0)
    deposito_origem = models.CharField(max_length=100)
    deposito_destino = models.CharField(max_length=100)
    pessoa = models.CharField(max_length=100)
    payload = models.JSONField(blank=True, null=True)
    resposta_api = models.JSONField(blank=True, null=True)
    chave_transferencia = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    erro = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    transferido_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ordem'], name='unique_transferencia_chapa_corte_ordem')
        ]
        ordering = ['-criado_em']

    def __str__(self):
        ordem = self.ordem.ordem or self.ordem.ordem_duplicada or self.ordem_id
        return f'{ordem} - {self.codigo_chapa or "sem codigo"} - {self.status}'

