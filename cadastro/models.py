from django.db import models

class Pecas(models.Model):

    SETOR_CHOICE = (('usinagem','Usinagem'),
                ('serra','Serra'),
                ('estamparia','Estamparia'),
                ('corte','Corte'),
                ('montagem','Montagem'),
                ('pintura','Pintura')
    )

    codigo = models.CharField(max_length=20)                                    
    descricao = models.CharField(max_length=255)
    materia_prima = models.CharField(max_length=100, blank=True, null=True)
    comprimento = models.FloatField(blank=True, null=True)
    setor = models.CharField(max_length=20, choices=SETOR_CHOICE)               

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['codigo','setor'], name='unique_codigo_setor')
        ]

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

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