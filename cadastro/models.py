from django.db import models

class Setor(models.Model):

    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):

        return self.nome

class Maquina(models.Model):

    nome = models.CharField(max_length=20, unique=True)
    setor = models.ManyToManyField(Setor, related_name='maquina_setor')

    def __str__(self):
        return self.nome

class Pecas(models.Model):

    codigo = models.CharField(max_length=255, unique=True)
    descricao = models.CharField(max_length=255, blank=True, null=True)
    materia_prima = models.CharField(max_length=100, blank=True, null=True)
    comprimento = models.FloatField(blank=True, null=True)
    setor = models.ManyToManyField(Setor, related_name='pecas_setor', blank=True)
    apelido = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['codigo'], name='unique_codigo')
        ]

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class MotivoInterrupcao(models.Model):
    
    nome = models.CharField(max_length=20, unique=True)
    setor = models.ManyToManyField(Setor, related_name='motivo_setor')

    def __str__(self):
        return self.nome

class Operador(models.Model):

    matricula = models.CharField(max_length=10)
    nome = models.CharField(max_length=20)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE ,related_name='operador_setor')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['matricula','setor'], name='operador_setor_unique')
        ]

    def __str__(self):
        return f'{self.matricula} - {self.nome}'
    
class Mp(models.Model):

    codigo = models.CharField(max_length=10)
    descricao = models.CharField(max_length=255)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='setor')

class Espessura(models.Model):

    nome=models.CharField(max_length=10, unique=True)

    def __str__(self):

        return self.nome
    
class Conjuntos(models.Model):

    codigo = models.CharField(max_length=10, unique=True)
    descricao = models.CharField(max_length=200, blank=True, null=True)
    # carretas que vai esse conjunto (campo ManyToMany)
