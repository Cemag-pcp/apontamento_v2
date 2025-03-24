from django.db import models
from django.utils.timezone import now

from cadastro.models import Pecas,Operador,Setor
from core.models import Ordem
from inspecao.models import DadosExecucaoInspecao

class PecasOrdem(models.Model):

    ordem=models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='ordem_pecas_estamparia')
    peca=models.ForeignKey(Pecas, on_delete=models.CASCADE, related_name='pecas_ordem_estamparia')
    qtd_planejada=models.FloatField()
    qtd_morta=models.FloatField(default=0)
    qtd_boa=models.FloatField(default=0)
    operador=models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador_produzido_estamparia', blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True, null=True, blank=True)

<<<<<<< HEAD

=======
class InfoAdicionaisInspecaoEstamparia(models.Model):

    dados_exec_inspecao = models.ForeignKey(DadosExecucaoInspecao, on_delete=models.CASCADE, null=False, blank=False)
    operador = models.ForeignKey(Operador, on_delete=models.SET_NULL, null=True, blank=True)
    destino = models.CharField(max_length=30, null=False, blank=False)
    inspecao_completa = models.BooleanField(default=False)
    qtd_mortas = models.IntegerField(default=0, null=False, blank=False)
    motivo_mortas = models.CharField(max_length=100, null=True, blank=True)
    ficha = models.ImageField(upload_to='ficha_estamparia/', null=True, blank=True)

class MedidasInspecaoEstamparia(models.Model):

    informacoes_adicionais_estamparia = models.ForeignKey(InfoAdicionaisInspecaoEstamparia, on_delete=models.CASCADE, null=False, blank=False)
    cabecalho_medida_a = models.CharField(max_length=10, null=True, blank=True)
    medida_a = models.FloatField(null=True, blank=True)
    cabecalho_medida_b = models.CharField(max_length=10, null=True, blank=True)
    medida_b = models.FloatField(null=True, blank=True)
    cabecalho_medida_c = models.CharField(max_length=10, null=True, blank=True)
    medida_c = models.FloatField(null=True, blank=True)
    cabecalho_medida_d = models.CharField(max_length=10, null=True, blank=True)
    medida_d = models.FloatField(null=True, blank=True)
>>>>>>> dev-saul
