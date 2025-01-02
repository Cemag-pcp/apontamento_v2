from django.db import models
from django.utils.timezone import now
from django.db.models import Max

from cadastro.models import MotivoInterrupcao,Mp,Operador

STATUS_ANDAMENTO_CHOICES = (
    ('aguardando_iniciar', 'Aguardando iniciar'),
    ('iniciada', 'Iniciada'),
    ('finalizada','Finalizada'),
    ('interrompida', 'Interrompida')
)

class Ordem(models.Model):

    MAQUINA_CHOICES = (
        ('laser_1', 'Laser 1'),
        ('laser_2', 'Laser 2 (JFY)'),
        ('plasma_1', 'Plasma 1'),
        ('plasma_2', 'Plasma 2'),
        ('prensa', 'Prensa'),
        ('furadeira_1', 'Furadeira 1'),
        ('furadeira_2', 'Furadeira 2'),
        ('furadeira_3', 'Furadeira 3'),
        ('furadeira_4', 'Furadeira 4'),
        ('furadeira_5', 'Furadeira 5'),
        ('furadeira_6', 'Furadeira 6'),
        ('furadeira_7', 'Furadeira 7'),
        ('centro_de_usinagem', 'Centro de usinagem'),
        ('serra_1','Serra 1'),
        ('serra_2','Serra 2'),
        ('serra_3','Serra 3'),
        ('torno_1', 'Torno 1'),
        ('torno_2', 'Torno 2'),
        ('chanfradeira', 'Chanfradeira'),
    )

    GRUPO_MAQUINA_CHOICES = (
        ('laser_1', 'Laser 1'),
        ('laser_2', 'Laser 2 (JFY)'),
        ('plasma', 'Plasma'),
        ('prensa', 'Prensa'),
        ('usinagem', 'Usinagem'),
        ('serra', 'Serra'),
    )

    ordem = models.IntegerField()
    data_criacao = models.DateTimeField(default=now, editable=False)
    obs = models.TextField(null=True, blank=True)
    grupo_maquina = models.CharField(max_length=20, choices=GRUPO_MAQUINA_CHOICES, blank=True, null=True)
    maquina = models.CharField(max_length=20, choices=MAQUINA_CHOICES, blank=True, null=True)
    status_atual = models.CharField(max_length=20, choices=STATUS_ANDAMENTO_CHOICES, default='aguardando_iniciar')
    status_prioridade = models.IntegerField(default=0)
    operador_final = models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador', blank=True, null=True)
    obs_operador = models.TextField(blank=True, null=True)
    data_programacao = models.DateField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ordem', 'maquina'], name='unique_ordem_processo')
        ]

    def save(self, *args, **kwargs):
        # Incrementa automaticamente apenas para os grupos diferentes de "Laser" e "Plasma"
        if not self.pk and self.grupo_maquina not in ['laser_1','laser_2','plasma']:
            # Busca o maior número de ordem dentro do mesmo grupo de máquina
            ultimo_numero = Ordem.objects.filter(grupo_maquina=self.grupo_maquina).aggregate(
                Max('ordem')
            )['ordem__max'] or 0  # Se não houver ordens, começa do 0
            self.ordem = ultimo_numero + 1

        super().save(*args, **kwargs)  # Salva normalmente

    def __str__(self):
        return f"Ordem {self.ordem} - {self.maquina}"

class PropriedadesOrdem(models.Model):

    TIPO_CHAPA_CHOICES=(('aco_carbono','Aço carbono'),
                        ('anti_derrapante','Anti derrapante'),
                        ('alta_resistencia','Alta resistência'))

    ordem = models.OneToOneField(Ordem,on_delete=models.CASCADE,related_name='propriedade')
    mp_codigo = models.ForeignKey(Mp, on_delete=models.CASCADE, related_name='mp', blank=True, null=True)
    descricao_mp=models.CharField(max_length=255, null=True, blank=True)
    tamanho=models.CharField(max_length=100, null=True, blank=True)
    espessura=models.CharField(max_length=20, null=True, blank=True)
    quantidade=models.FloatField()
    aproveitamento=models.CharField(max_length=10, null=True, blank=True)
    tipo_chapa = models.CharField(max_length=20, choices=TIPO_CHAPA_CHOICES, null=True, blank=True)
    retalho = models.BooleanField(default=False)
    nova_mp = models.ForeignKey(Mp, on_delete=models.CASCADE, related_name='nova_mp', blank=True, null=True) # caso o usuario opte por mudar ao finalizar a ordem

class OrdemProcesso(models.Model):
    
    ordem = models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='processos')
    status = models.CharField(max_length=20, choices=STATUS_ANDAMENTO_CHOICES)
    data_inicio = models.DateTimeField(default=now)  # Armazena quando o status foi definido
    data_fim = models.DateTimeField(null=True, blank=True)  # Armazena quando o status foi finalizado
    motivo_interrupcao = models.ForeignKey(MotivoInterrupcao, on_delete=models.CASCADE, null=True, blank=True)

    def finalizar_atual(self):
        """
        Finaliza o processo atual registrando a data de fim.
        """
        self.data_fim = now()
        self.save()

    @staticmethod
    def criar_proximo_processo(ordem, novo_status):
        """
        Finaliza o processo atual da ordem e cria um novo com o próximo status.
        """
        # Finaliza o processo atual
        processo_atual = ordem.processos.filter(data_fim__isnull=True).first()
        if processo_atual:
            processo_atual.finalizar_atual()

        # Cria o novo processo
        novo_processo = OrdemProcesso.objects.create(
            ordem=ordem,
            status=novo_status,
            data_inicio=now()
        )
        return novo_processo

