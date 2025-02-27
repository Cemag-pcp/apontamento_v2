from django.db import models
from core.models import Profile

class Inspecao(models.Model):

    ordem = models.ForeignKey('Ordem', on_delete=models.CASCADE, related_name='inspecoes')
    data_inspecao = models.DateTimeField(auto_now_add=True)

    # Chaves estrangeiras opcionais para cada setor
    pecas_ordem_pintura = models.ForeignKey('apontamento_pintura.PecasOrdem', on_delete=models.CASCADE, null=True, blank=True)
    pecas_ordem_montagem = models.ForeignKey('apontamento_montagem.PecasOrdem', on_delete=models.CASCADE, null=True, blank=True)
    pecas_ordem_estamparia = models.ForeignKey('apontamento_estamparia.PecasOrdem', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Inspeção {self.id} - Ordem {self.ordem.id} - Setor {self.setor}"
    
class DadosExecucaoInspecao(models.Model):

    inspecao = models.ForeignKey(Inspecao, on_delete=models.CASCADE, null=False, blank=False)
    inspetor = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=False, blank=False)
    data_execucao = models.DateTimeField(auto_now_add=True)
    num_execucao = models.IntegerField(null=False, blank=False)
    conformidade = models.IntegerField(null=False, blank=False)
    nao_conformidade = models.IntegerField(null=False, blank=False)
    observacao = models.CharField(max_length=150, null=True, blank=True)


class Reinspecao(models.Model):

    dados_execucao = models.ForeignKey(DadosExecucaoInspecao, on_delete=models.CASCADE, null=False, blank=False)
    data_reinspecao = models.DateTimeField(auto_now_add=True)


class Causas(models.Model):

    nome = models.CharField(max_length=40, null=False, blank=False)
    setor = models.CharField(max_length=40, null=False, blank=False)

    def __str__(self):
        return f"{self.nome} cadastrada para o setor {self.setor}"

class CausasNaoConformidade(models.Model):
        
    dados_execucao = models.ForeignKey(DadosExecucaoInspecao, on_delete=models.CASCADE, null=False, blank=False)
    causa = models.ForeignKey(Causas, null=False, blank=False)
    foto = models.CharField(max_length=255, null=False, blank=False)
    quantidade = models.IntegerField(null=False, blank=False)