from django.db import models
from django.utils.timezone import now

from cadastro.models import Pecas
from core.models import Ordem
from inspecao.models import DadosExecucaoInspecao


class PecasOrdem(models.Model):

    ordem = models.ForeignKey(
        Ordem, on_delete=models.CASCADE, related_name="ordem_pecas_serra"
    )
    peca = models.ForeignKey(
        Pecas, on_delete=models.CASCADE, related_name="pecas_ordem_serra"
    )
    qtd_planejada = models.FloatField()
    qtd_morta = models.FloatField(default=0)
    qtd_boa = models.FloatField(default=0)
    data = models.DateTimeField(auto_now=True, null=True, blank=True)


class InfoAdicionaisSerraUsinagem(models.Model):
    dados_exec_inspecao = models.OneToOneField(
        DadosExecucaoInspecao, on_delete=models.CASCADE, related_name="info_adicionais"
    )
    inspecao_completa = models.BooleanField(default=False)
    autoinspecao_noturna = models.BooleanField(default=False)
    ficha = models.ImageField(upload_to="fichas_inspecao/", null=True, blank=True)

    observacoes_gerais = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Informação Adicional"
        verbose_name_plural = "Informações Adicionais"

    def __str__(self):
        return f"Info Adicional - Execução {self.dados_exec_inspecao.num_execucao}"


class MedidasProcesso(models.Model):
    TIPO_PROCESSO_CHOICES = [
        ("serra", "Serra"),
        ("usinagem", "Usinagem"),
        ("furacao", "Furação"),
    ]

    # Relacionamento com a execução principal
    execucao = models.ForeignKey(
        DadosExecucaoInspecao, on_delete=models.CASCADE, related_name="medidas_processo"
    )

    info_adicionais = models.ForeignKey(
        InfoAdicionaisSerraUsinagem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="medidas",
    )

    tipo_processo = models.CharField(max_length=10, choices=TIPO_PROCESSO_CHOICES)
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_registro"]

    def save(self, *args, **kwargs):
        # Auto-relaciona com as info adicionais se existirem
        if not self.info_adicionais and hasattr(self.execucao, "info_adicionais"):
            self.info_adicionais = self.execucao.info_adicionais
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Medição {self.id} - {self.get_tipo_processo_display()}"
