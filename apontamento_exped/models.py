from django.db import models

from core.models import Profile

class Carga(models.Model):
    nome = models.CharField(max_length=100)  # Ex: Carga 123
    data_criacao = models.DateTimeField(auto_now_add=True)
    responsavel_criacao = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, choices=[('pendente', 'Pendente'), ('ok', 'Confirmado'), ('erro', 'Erro identificado')], default='pendente')

    def __str__(self):
        return self.nome

class Pacote(models.Model):
    numero = models.CharField(max_length=100, unique=True)  # Ex: CLIENTE_X_001
    carga = models.ForeignKey(Carga, related_name='pacotes', on_delete=models.CASCADE)
    criado_por = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    confirmado_por = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmou_pacotes')
    data_confirmacao = models.DateTimeField(null=True, blank=True)
    status_confirmacao = models.CharField(max_length=50, choices=[('pendente', 'Pendente'), ('ok', 'Confirmado'), ('erro', 'Erro identificado')], default='pendente')

    def __str__(self):
        return self.numero

class ItemPacote(models.Model):
    pacote = models.ForeignKey(Pacote, related_name='itens', on_delete=models.CASCADE)
    codigo_peca = models.CharField(max_length=50)
    descricao = models.CharField(max_length=200)
    cor = models.CharField(max_length=50)
    quantidade = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.codigo_peca} - {self.cor}"

class VerificacaoPacote(models.Model):
    pacote = models.OneToOneField(Pacote, on_delete=models.CASCADE, related_name='verificacao')
    verificado_por = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    data_verificacao = models.DateTimeField(auto_now_add=True)
    tudo_correto = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)  # Caso algo esteja errado, detalha aqui

    def __str__(self):
        return f"Verificação do {self.pacote.numero}"
