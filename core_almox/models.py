from django.conf import settings
from django.db import models


class RegistroAcaoSolicitacaoAlmox(models.Model):
    ACAO_CHOICES = [
        ("edicao", "Edicao"),
        ("exclusao", "Exclusao"),
    ]

    TIPO_CHOICES = [
        ("requisicao", "Requisicao"),
        ("transferencia", "Transferencia"),
    ]

    tipo_solicitacao = models.CharField(max_length=20, choices=TIPO_CHOICES)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    solicitacao_id_original = models.PositiveIntegerField()
    motivo = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_acao_almox",
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_criacao"]
        verbose_name = "Registro de acao do almoxarifado"
        verbose_name_plural = "Registros de acoes do almoxarifado"

    def __str__(self):
        return f"{self.tipo_solicitacao} #{self.solicitacao_id_original} - {self.acao}"
