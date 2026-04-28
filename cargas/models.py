import uuid

from django.conf import settings
from django.db import models


class LinkAcompanhamento(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    data_carga = models.DateField()
    cliente = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["data_carga", "cliente"],
                name="uq_link_acompanhamento_data_cliente",
            )
        ]

    def __str__(self):
        return f"{self.cliente} - {self.data_carga}"


class CargaLiberada(models.Model):
    carga_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    data_carga = models.DateField()
    carga_nome = models.CharField(max_length=100)
    data_sugerida_planejamento = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["data_carga", "carga_nome"],
                name="uq_carga_liberada_data_nome",
            )
        ]
        ordering = ["-data_carga", "carga_nome"]

    def __str__(self):
        return f"{self.data_carga} - {self.carga_nome}"


class CargaLiberadaVersao(models.Model):
    carga_liberada = models.ForeignKey(
        CargaLiberada,
        on_delete=models.CASCADE,
        related_name="versoes",
    )
    versao = models.PositiveIntegerField()
    versao_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    data_inicio_pesquisa = models.DateField()
    data_fim_pesquisa = models.DateField()
    liberado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cargas_liberadas_versoes",
    )
    liberado_em = models.DateTimeField(auto_now_add=True)
    payload_snapshot = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["carga_liberada", "versao"],
                name="uq_carga_liberada_versao",
            )
        ]
        ordering = ["carga_liberada_id", "-versao"]

    def __str__(self):
        return f"{self.carga_liberada} v{self.versao}"


class CargaLiberadaItem(models.Model):
    carga_versao = models.ForeignKey(
        CargaLiberadaVersao,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    codigo_recurso = models.CharField(max_length=255)
    quantidade = models.FloatField()
    presente_no_carreta = models.CharField(max_length=5, blank=True, default="")
    cliente = models.CharField(max_length=255, blank=True, default="")
    cliente_codigo = models.CharField(max_length=255, blank=True, default="")
    numero_serie = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["codigo_recurso"]

    def __str__(self):
        return f"{self.codigo_recurso} ({self.quantidade})"


class CargaLiberadaAlteracao(models.Model):
    TIPO_ALTERACAO_CHOICES = [
        ("item_adicionado", "Item adicionado"),
        ("item_removido", "Item removido"),
        ("quantidade_alterada", "Quantidade alterada"),
        ("liberacao_inicial", "Liberação inicial"),
    ]

    carga_liberada = models.ForeignKey(
        CargaLiberada,
        on_delete=models.CASCADE,
        related_name="alteracoes",
    )
    versao_origem = models.ForeignKey(
        CargaLiberadaVersao,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alteracoes_origem",
    )
    versao_destino = models.ForeignKey(
        CargaLiberadaVersao,
        on_delete=models.CASCADE,
        related_name="alteracoes_destino",
    )
    tipo_alteracao = models.CharField(max_length=30, choices=TIPO_ALTERACAO_CHOICES)
    codigo_recurso = models.CharField(max_length=255, blank=True)
    quantidade_anterior = models.FloatField(null=True, blank=True)
    quantidade_nova = models.FloatField(null=True, blank=True)
    detalhes = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.carga_liberada} - {self.tipo_alteracao}"
