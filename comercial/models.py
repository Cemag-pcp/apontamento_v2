from django.contrib.auth.models import User
from django.db import models


class ConferenciaPedido(models.Model):
    chave_pedido = models.CharField(max_length=100)
    deal_id = models.CharField(max_length=100)
    quote_id = models.CharField(max_length=100)
    data_criacao = models.CharField(max_length=100, blank=True)
    contato = models.CharField(max_length=255, blank=True)
    observacao = models.TextField(blank=True)
    itens = models.JSONField(default=list)
    conferido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='conferencias_pedido',
    )
    conferido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['chave_pedido', 'deal_id', 'quote_id'],
                name='unique_conferencia_pedido',
            )
        ]
        ordering = ['-conferido_em']

    def __str__(self):
        return f'{self.chave_pedido} / {self.quote_id}'
