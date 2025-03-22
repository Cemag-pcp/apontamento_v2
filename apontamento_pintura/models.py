from django.db import models
from django.utils.timezone import now

from core.models import Ordem
from cadastro.models import Operador
from inspecao.models import Reinspecao

class PecasOrdem(models.Model):
    ordem = models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_pintura')
    peca = models.CharField(max_length=255)
    qtd_planejada = models.FloatField()
    qtd_morta = models.FloatField(default=0)
    qtd_boa = models.FloatField(default=0)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    tipo = models.CharField(max_length=20)  # PÓ ou PU
    operador_fim=models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador_fim_pintura', blank=True, null=True)

    def __str__(self):
        return f"{self.peca} - {self.qtd_boa}/{self.qtd_planejada}"

class Cambao(models.Model):
    cor = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='livre')  # 'livre', 'em uso', 'finalizado'
    tipo = models.CharField(max_length=20)  # PÓ ou PU

    def __str__(self):
        return f"Cambão {self.id} - {self.cor} ({self.status})"

class CambaoPecas(models.Model):
    cambao = models.ForeignKey(Cambao, on_delete=models.CASCADE, related_name='pecas_no_cambao')
    peca_ordem = models.ForeignKey(PecasOrdem, on_delete=models.CASCADE, related_name='cambao_peca_ordem_pintura')
    quantidade_pendurada = models.FloatField(default=0)
    data_pendura = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pendurada')  # 'pendurada', 'finalizada'
    data_fim = models.DateTimeField(null=True, blank=True)
    operador_inicio=models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador_produzido_pintura', blank=True, null=True)

    def __str__(self):
        return f"{self.peca_ordem.peca} - {self.quantidade_pendurada}"

class Retrabalho(models.Model):
    TIPO_CHOICES = (
        ("a retrabalhar", "A Retrabalhar"),
        ("em processo", "Em processo"),
        ("finalizado", "Finalizado"),
    )

    reinspecao = models.ForeignKey(Reinspecao, on_delete=models.CASCADE, null=False, blank=False)
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20,choices=TIPO_CHOICES, null=False, blank=False)