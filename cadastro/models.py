from django.db import models

class Processo(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nome

class Maquina(models.Model):

    SETOR_CHOICE = (('usinagem','Usinagem'),
                    ('serra','Serra'),
                    ('estamparia','Estamparia'),
                    ('corte','Corte'),
                    ('montagem','Montagem'),
                    ('pintura','Pintura')
    )

    nome = models.CharField(max_length=20, unique=True)
    setor = models.CharField(max_length=20, choices=SETOR_CHOICE)

    def __str__(self):
        return self.nome

class Pecas(models.Model):

    SETOR_CHOICE = (('usinagem','Usinagem'),
                ('serra','Serra'),
                ('estamparia','Estamparia'),
                ('corte','Corte'),
                ('montagem','Montagem'),
                ('pintura','Pintura')
    )

    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.CharField(max_length=255)
    materia_prima = models.CharField(max_length=100, blank=True, null=True)
    comprimento = models.FloatField(blank=True, null=True)
    processos = models.ManyToManyField(Processo, related_name='pecas')
    maquinas = models.ManyToManyField(Maquina, related_name='maquinas')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['codigo'], name='unique_codigo')
        ]

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class PecaProcesso(models.Model):
    peca = models.ForeignKey(Pecas, on_delete=models.CASCADE)
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE)
    ordem = models.PositiveIntegerField()

    class Meta:
        unique_together = ('peca', 'processo', 'ordem')
        ordering = ['ordem']

    def __str__(self):
        return f'{self.peca.codigo} - {self.processo.nome} (Ordem: {self.ordem})'

class PecaMaquina(models.Model):
    STATUS_CHOICES = (
        ('pendente', 'Pendente'),
        ('em_progresso', 'Em Progresso'),
        ('concluido', 'Concluído'),
    )

    peca_processo = models.ForeignKey(PecaProcesso, on_delete=models.CASCADE)
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE)
    ordem = models.PositiveIntegerField()

    class Meta:
        unique_together = ('peca_processo', 'maquina')
        ordering = ['ordem']

    def __str__(self):
        return f'{self.peca_processo} - Máquina: {self.maquina.nome} (Ordem: {self.ordem})'

class MotivoInterrupcao(models.Model):
    
    SETOR_CHOICE = (('usinagem','Usinagem'),
                    ('serra','Serra'),
                    ('estamparia','Estamparia'),
                    ('corte','Corte'),
                    ('montagem','Montagem'),
                    ('pintura','Pintura')
    )

    nome = models.CharField(max_length=20, unique=True)
    setor = models.CharField(max_length=20, choices=SETOR_CHOICE)

    def __str__(self):
        return self.nome

class Operador(models.Model):

    SETOR_CHOICE = (('usinagem','Usinagem'),
                    ('serra','Serra'),
                    ('estamparia','Estamparia'),
                    ('corte','Corte'),
                    ('montagem','Montagem'),
                    ('pintura','Pintura')
    )

    matricula = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=20)
    setor = models.CharField(max_length=20, choices=SETOR_CHOICE)

    def __str__(self):
        return f'{self.matricula} - {self.nome}'