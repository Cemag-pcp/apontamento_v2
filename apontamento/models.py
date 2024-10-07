from django.db import models
from django.utils import timezone

from cadastro.models import *

class Planejamento(models.Model):

    TIPO_CHOICES = (
        ('planejamento', 'Planejamento'),
        ('fora_do_planejamento', 'Fora do planejamento')
    )

    STATUS_ANDAMENTO_CHOICES = (
        ('aguardando_iniciar', 'Aguardando iniciar'),
        ('iniciada', 'Iniciada'),
        ('finalizada','Finalizada'),
        ('interrompida', 'Interrompida')
    )

    data_planejada = models.DateField()
    tipo_planejamento = models.CharField(max_length=20, choices=TIPO_CHOICES, default='planejamento')
    status_andamento = models.CharField(max_length=20, choices=STATUS_ANDAMENTO_CHOICES, default='aguardando_iniciar')
    tamanho_vara = models.CharField(max_length=20, null=True, blank=True)
    quantidade_vara = models.CharField(max_length=20,blank=True, null=True)
    mp_usada = models.CharField(max_length=200, blank=True, null=True)
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='planejamento_setor')

    def __str__(self):
        return f'Planejamento para {self.data_planejada}'

class PlanejamentoPeca(models.Model):
    planejamento = models.ForeignKey(Planejamento, on_delete=models.CASCADE, related_name='pecas_planejadas')
    peca = models.ForeignKey(PecaProcesso, on_delete=models.CASCADE, related_name='planejamento_peca')
    quantidade_planejada = models.PositiveIntegerField()
    quantidade_produzida = models.PositiveIntegerField(default=0)
    quantidade_morta = models.PositiveIntegerField(default=0)
    ordem = models.IntegerField(default=1)

    def __str__(self):
        return f'{self.peca} - {self.quantidade_planejada}'

class Apontamento(models.Model):
    STATUS_CHOICES = (
        ('iniciado', 'Iniciado'),
        ('interrompido', 'Interrompido'),
        ('finalizado', 'Finalizado'),
        ('parcial', 'Finalizado Parcialmente'),
    )

    planejamento = models.ForeignKey(Planejamento, on_delete=models.CASCADE, related_name='apontamento_planejamento')
    data_apontamento = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='iniciado')
    observacao = models.TextField(blank=True, null=True)
    operador = models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='apontamento_operador')
    
    data_inicio = models.DateTimeField(blank=True, null=True)
    data_finalizacao = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Apontamento de {self.planejamento} em {self.data_apontamento}'

    def finalizar(self):
        """Método para finalizar a ordem e planejar o próximo processo."""
        self.status = 'finalizado'
        self.data_finalizacao = timezone.now()
        self.save()

        # Planejar o próximo processo e máquina automaticamente
        self.planejar_proximo_processo()

    def interromper(self, motivo_interrupcao):
        """Método para interromper a ordem e registrar o motivo."""
        self.status = 'interrompido'
        self.save()

        # Cria um novo registro de interrupção
        Interrupcao.objects.create(
            apontamento=self,
            motivo=motivo_interrupcao,
            data_interrupcao=timezone.now()
        )

    def retornar(self):
        """Método para retornar a produção após interrupção."""
        # Encontra a última interrupção que não tem data de retorno
        ultima_interrupcao = self.interrupcoes.filter(data_retorno__isnull=True).last()

        if ultima_interrupcao:
            # Define a data de retorno na interrupção
            ultima_interrupcao.data_retorno = timezone.now()
            ultima_interrupcao.save()

        # Atualiza o status do apontamento
        self.status = 'iniciado'
        self.save()

    def finalizar(self):
        """Método para finalizar a ordem."""
        self.status = 'finalizado'
        self.data_finalizacao = timezone.now()
        self.save()

class Interrupcao(models.Model):
    apontamento = models.ForeignKey(Apontamento, on_delete=models.CASCADE, related_name='interrupcoes')
    motivo = models.ForeignKey(MotivoInterrupcao, on_delete=models.CASCADE)
    data_interrupcao = models.DateTimeField()
    data_retorno = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Interrupção: {self.motivo} em {self.data_interrupcao}'

class OrdemPadrao(models.Model):

    numero_ordem = models.PositiveIntegerField(unique=True, editable=False)
    descricao = models.TextField(blank=True, null=True)
    pecas = models.ManyToManyField(PecaProcesso, related_name='ordens_padroes')
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Ordem {self.numero_ordem}'

    def save(self, *args, **kwargs):
        if not self.numero_ordem:
            # Se o número da ordem ainda não foi gerado, criar o próximo número sequencial
            ultima_ordem = OrdemPadrao.objects.all().order_by('numero_ordem').last()
            if ultima_ordem:
                self.numero_ordem = ultima_ordem.numero_ordem + 1
            else:
                self.numero_ordem = 1  # Se for a primeira ordem, começar em 1
        super(OrdemPadrao, self).save(*args, **kwargs)
