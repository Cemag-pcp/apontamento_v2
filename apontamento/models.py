from django.db import models
from django.utils import timezone

from cadastro.models import *

class Planejamento(models.Model):
    SETOR_CHOICE = (
        ('usinagem', 'Usinagem'),
        ('serra', 'Serra'),
        ('estamparia', 'Estamparia'),
        ('corte', 'Corte'),
        ('montagem', 'Montagem'),
        ('pintura', 'Pintura')
    )

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
    # maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='planejamento_maquina', blank=True, null=True)
    tipo_planejamento = models.CharField(max_length=20, choices=TIPO_CHOICES, default='planejamento')
    status_andamento = models.CharField(max_length=20, choices=STATUS_ANDAMENTO_CHOICES, default='aguardando_iniciar')
    tamanho_vara = models.CharField(max_length=20, null=True, blank=True)
    quantidade_vara = models.PositiveIntegerField(blank=True, null=True)
    mp_usada = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f'Planejamento para {self.data_planejada}'

class PlanejamentoPeca(models.Model):
    planejamento = models.ForeignKey(Planejamento, on_delete=models.CASCADE, related_name='pecas_planejadas')
    peca = models.ForeignKey(Pecas, on_delete=models.CASCADE, related_name='planejamento_peca')
    quantidade_planejada = models.PositiveIntegerField()
    quantidade_produzida = models.PositiveIntegerField(default=0)
    quantidade_morta = models.PositiveIntegerField(default=0)

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

    # def planejar_proximo_processo(self):
    #     """Método para planejar o próximo processo e máquina."""
    #     # Obter o processo atual da peça a partir do planejamento
    #     peca_planejada_atual = self.planejamento.pecas_planejadas.first()
    #     peca_processo_atual = PecaProcesso.objects.filter(
    #         peca=peca_planejada_atual.peca,
    #         processo__nome=self.planejamento.maquina.setor
    #     ).first()

    #     if peca_processo_atual:
    #         # Encontrar o próximo processo na ordem
    #         proximo_processo = PecaProcesso.objects.filter(
    #             peca=peca_processo_atual.peca,
    #             ordem__gt=peca_processo_atual.ordem
    #         ).order_by('ordem').first()

    #         if proximo_processo:
    #             # Encontrar a máquina associada ao próximo processo
    #             maquina_proxima = PecaMaquina.objects.filter(
    #                 peca_processo=proximo_processo
    #             ).order_by('ordem').first().maquina

    #             # Criar um novo planejamento para o próximo processo
    #             Planejamento.objects.create(
    #                 data_planejada=timezone.now(),
    #                 maquina=maquina_proxima,
    #                 setor=maquina_proxima.setor,
    #                 tipo_planejamento='planejamento',
    #                 status_andamento='aguardando_iniciar'
    #             )

class Interrupcao(models.Model):
    apontamento = models.ForeignKey(Apontamento, on_delete=models.CASCADE, related_name='interrupcoes')
    motivo = models.ForeignKey(MotivoInterrupcao, on_delete=models.CASCADE)
    data_interrupcao = models.DateTimeField()
    data_retorno = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Interrupção: {self.motivo} em {self.data_interrupcao}'
