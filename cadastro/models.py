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

    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.CharField(max_length=255)
    materia_prima = models.CharField(max_length=100, blank=True, null=True)
    comprimento = models.FloatField(blank=True, null=True)
    setor = models.ManyToManyField(Setor, related_name='pecas_setor')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['codigo'], name='unique_codigo')
        ]

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class PecaProcesso(models.Model):
    peca = models.ForeignKey(Pecas, on_delete=models.CASCADE)
    processo = models.ForeignKey(Setor, on_delete=models.CASCADE)
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE)
    ordem = models.PositiveIntegerField()

    class Meta:
        unique_together = ('peca', 'processo', 'ordem')
        ordering = ['ordem']

    def __str__(self):
        return f'{self.peca.codigo} - {self.processo.nome} (Ordem: {self.ordem})'

class MotivoInterrupcao(models.Model):
    
    nome = models.CharField(max_length=20, unique=True)
    setor = models.ManyToManyField(Setor, related_name='motivo_setor')

    def __str__(self):
        return self.nome

class Operador(models.Model):

    matricula = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=20)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE ,related_name='operador_setor')

    def __str__(self):
        return f'{self.matricula} - {self.nome}'