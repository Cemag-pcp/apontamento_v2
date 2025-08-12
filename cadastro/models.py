from django.db import models

class Setor(models.Model):

    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):

        return self.nome

class Processo(models.Model):

    nome = models.CharField(max_length=20,unique=True)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE)

class Maquina(models.Model):

    nome = models.CharField(max_length=100)
    setor = models.ForeignKey(Setor, related_name='maquina_setor', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['nome','setor','tipo'], name='unique_nome_setor_maquina_tipo')
        ]

    def __str__(self):
        return self.nome

class MotivoInterrupcao(models.Model):
    
    nome = models.CharField(max_length=50, unique=True)
    setor = models.ManyToManyField(Setor, related_name='motivo_setor')
    visivel = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

class MotivoMaquinaParada(models.Model):
    
    nome = models.CharField(max_length=20, unique=True)
    setor = models.ManyToManyField(Setor, related_name='motivo_maq_parada_setor')
    visivel = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

class MotivoExclusao(models.Model):

    nome = models.CharField(max_length=20, unique=True)
    setor = models.ManyToManyField(Setor, related_name='motivo_exclusao_setor')

    def __str__(self):
        return self.nome

class Operador(models.Model):

    STATUS_CHOICES = (('ativo','Ativo'),
                      ('inativo','Inativo'))

    matricula = models.CharField(max_length=10)
    nome = models.CharField(max_length=20)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='operador_setor')
    maquinas = models.ManyToManyField(Maquina, related_name='operadores', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')

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

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class Espessura(models.Model):

    nome=models.CharField(max_length=10, unique=True)

    def __str__(self):

        return self.nome

class Carretas(models.Model):

    codigo = models.CharField(max_length=250, unique=True)
    descricao = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class Conjuntos(models.Model):
    codigo = models.CharField(max_length=255)
    descricao = models.CharField(max_length=200, blank=True, null=True)
    quantidade = models.IntegerField() # quantidade por carreta
    carreta = models.ManyToManyField('Carretas', through='ConjuntoCarreta', blank=True)

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class ConjuntoCarreta(models.Model):
    conjunto = models.ForeignKey(Conjuntos, on_delete=models.CASCADE)
    carreta = models.ForeignKey(Carretas, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['conjunto', 'carreta'], name='unique_conjunto_carreta')
        ]

class Pecas(models.Model):

    codigo = models.CharField(max_length=255, unique=True)
    descricao = models.CharField(max_length=255, blank=True, null=True)
    materia_prima = models.CharField(max_length=100, blank=True, null=True)
    comprimento = models.FloatField(blank=True, null=True)
    setor = models.ManyToManyField(Setor, related_name='pecas_setor', blank=True)
    apelido = models.CharField(max_length=255, blank=True, null=True)
    conjunto = models.ForeignKey(Conjuntos, on_delete=models.CASCADE, related_name='peca_conjunto', null=True, blank=True)
    # caso tenha processo preestabelecido para peça
    processo_1 = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='processo_maquina_1', blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['codigo','conjunto'], name='unique_codigo_conjunto')
        ]

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'
    
class PecasEstanqueidade(models.Model):

    TIPO_CHOICES = (
        ("tanque", "Tanque"), 
        ("tubo", "Tubo"), 
        ("cilindro", "Cilindro")
    )

    codigo = models.CharField(max_length=255, unique=True)
    descricao = models.CharField(max_length=255, blank=True, null=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, null=False, blank=False)

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

class CarretasExplodidas(models.Model):

    codigo_peca = models.CharField(max_length=250, blank=True, null=True)
    descricao_peca = models.CharField(max_length=255, blank=True, null=True)
    mp_peca = models.CharField(max_length=255, blank=True, null=True)
    total_peca = models.CharField(max_length=10, blank=True, null=True)
    conjunto_peca = models.CharField(max_length=255, blank=True, null=True)
    primeiro_processo = models.CharField(max_length=255, blank=True, null=True)
    segundo_processo = models.CharField(max_length=255, blank=True, null=True)
    carreta = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f'{self.descricao_peca}'
