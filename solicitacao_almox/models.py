from django.db import models

from cadastro_almox.models import (
    Cc,
    Funcionario,
    ItensSolicitacao,
    ClasseRequisicao,
    DepositoDestino,
    ItensTransferencia,
    OperadorAlmox,
)

import datetime


class SolicitacaoRequisicao(models.Model):
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="requisicao_funcionario"
    )
    cc = models.ForeignKey(Cc, on_delete=models.CASCADE, related_name="requisicao_cc")
    item = models.ForeignKey(
        ItensSolicitacao, on_delete=models.CASCADE, related_name="requisicao_itens"
    )
    classe_requisicao = models.ForeignKey(
        ClasseRequisicao, on_delete=models.CASCADE, related_name="requisicao_classe"
    )
    quantidade = models.FloatField()
    obs = models.TextField(blank=True, null=True)
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    entregue_por = models.ForeignKey(
        OperadorAlmox,
        on_delete=models.CASCADE,
        related_name="requisicao_operador",
        null=True,
        blank=True,
    )
    data_entrega = models.DateTimeField(null=True, blank=True)
    rpa = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.funcionario} - {self.item} - {self.classe_requisicao}"


class SolicitacaoTransferencia(models.Model):

    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="transferencia_funcionario"
    )
    deposito_destino = models.ForeignKey(
        DepositoDestino,
        on_delete=models.CASCADE,
        related_name="transferencia_deposito_destino",
    )
    item = models.ForeignKey(
        ItensTransferencia, on_delete=models.CASCADE, related_name="transferencia_itens"
    )
    quantidade = models.FloatField()
    obs = models.TextField(blank=True, null=True)
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    entregue_por = models.ForeignKey(
        OperadorAlmox,
        on_delete=models.CASCADE,
        related_name="transferencia_operador",
        null=True,
        blank=True,
    )
    data_entrega = models.DateTimeField(null=True, blank=True)
    rpa = models.TextField(null=True, blank=True)

    def __str__(self):

        return f"{self.funcionario} - {self.item}"


class SolicitacaoCadastroItem(models.Model):

    tipo_solicitacao = models.CharField(max_length=20)
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="cadastro_item"
    )
    codigo = models.CharField(max_length=100, blank=True, null=True)
    descricao = models.CharField(max_length=100, blank=True, null=True)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    deposito_destino = models.ForeignKey(
        DepositoDestino,
        on_delete=models.CASCADE,
        related_name="solicitacao_deposito_destino",
        null=True,
        blank=True,
    )
    cc = models.ForeignKey(
        Cc, on_delete=models.CASCADE, related_name="cadastro_cc", blank=True, null=True
    )
    aprovado = models.BooleanField(default=False)
    data_aprovacao = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.aprovado and not self.data_aprovacao:
            self.data_aprovacao = datetime.datetime.now()
        super(SolicitacaoCadastroItem, self).save(*args, **kwargs)


class SolicitacaoNovaMatricula(models.Model):

    matricula = models.CharField(max_length=20)
    nome = models.CharField(max_length=100)
    cc = models.ForeignKey(
        Cc, on_delete=models.CASCADE, related_name="solicitacao_cadastro_cc"
    )

    aprovado = models.BooleanField(default=False)
    data_aprovacao = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.aprovado and not self.data_aprovacao:
            self.data_aprovacao = datetime.datetime.now()
        super(SolicitacaoNovaMatricula, self).save(*args, **kwargs)
