from django.db import models
from django.utils.timezone import now
from django.db.models import Max
from django.contrib.auth.models import User

from cadastro.models import MotivoInterrupcao,Mp,Operador,MotivoMaquinaParada,MotivoExclusao,Maquina,Pecas,Setor

from datetime import timedelta

STATUS_ANDAMENTO_CHOICES = (
    ('aguardando_iniciar', 'Aguardando iniciar'),
    ('iniciada', 'Iniciada'),
    ('finalizada','Finalizada'),
    ('interrompida', 'Interrompida'),
    ('agua_prox_proc','Aguardando prox processo')
)

MAQUINA_CHOICES = (
    #Corte
    ('laser_1', 'Laser 1'),
    ('laser_2', 'Laser 2 (JFY)'),
    ('plasma_1', 'Plasma 1'),
    ('plasma_2', 'Plasma 2'),
    ('prensa', 'Prensa'),
    #Serra
    ('serra_1','Serra 1'),
    ('serra_2','Serra 2'),
    ('serra_3','Serra 3'),
    #Usinagem
    ('furadeira_1', 'Furadeira 1'),
    ('furadeira_2', 'Furadeira 2'),
    ('furadeira_3', 'Furadeira 3'),
    ('furadeira_4', 'Furadeira 4'),
    ('furadeira_5', 'Furadeira 5'),
    ('furadeira_6', 'Furadeira 6'),
    ('furadeira_7', 'Furadeira 7'),
    ('centro_de_usinagem', 'Centro de usinagem'),
    ('torno_1', 'Torno 1'),
    ('torno_2', 'Torno 2'),
    ('chanfradeira', 'Chanfradeira'),
    ('furar', 'Furar'),
    ('chanfrar','Chanfrar'),
    ('tornear',' Tornear'),
    #Estamparia
    ('viradeira_1','Viradeira 1'),
    ('viradeira_2','Viradeira 2'),
    ('viradeira_3','Viradeira 3'),
    ('viradeira_4','Viradeira 4'),
    ('viradeira_5','Viradeira 5'),
    ('prensa','Prensa'),
    #Prod especiais
    ('maq_solda', 'Máquina de solda'),

)

class Ordem(models.Model):

    GRUPO_MAQUINA_CHOICES = (
        ('laser_1', 'Laser 1'),
        ('laser_2', 'Laser 2 (JFY)'),
        ('plasma', 'Plasma'),
        ('prensa', 'Prensa'),
        ('usinagem', 'Usinagem'),
        ('serra', 'Serra'),
        ('prod_esp', 'Prod. Especiais'),
        ('estamparia', 'Estamparia'),
        ('montagem', 'Montagem'),
        ('pintura','Pintura')
    )

    ordem = models.IntegerField(blank=True, null=True)
    data_criacao = models.DateTimeField(default=now, editable=False)
    obs = models.TextField(null=True, blank=True)
    grupo_maquina = models.CharField(max_length=20, choices=GRUPO_MAQUINA_CHOICES, blank=True, null=True)
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='maquina_ordem', blank=True, null=True)#models.CharField(max_length=20, choices=MAQUINA_CHOICES, blank=True, null=True)
    status_atual = models.CharField(max_length=20, choices=STATUS_ANDAMENTO_CHOICES, default='aguardando_iniciar')
    status_prioridade = models.IntegerField(default=0)
    operador_final = models.ForeignKey(Operador, on_delete=models.CASCADE, related_name='operador', blank=True, null=True)
    obs_operador = models.TextField(blank=True, null=True)
    data_programacao = models.DateField(blank=True, null=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    excluida = models.BooleanField(default=False) # Opção para exclusão de ordens
    motivo_exclusao = models.ForeignKey(MotivoExclusao, on_delete=models.CASCADE, null=True, blank=True) # Caso exclua a ordem, é necessário informar o motivo
    
    #Para ordens duplicadas de corte
    ordem_duplicada = models.TextField(blank=True, null=True) # Armazena a identificação da ordem duplicada (Ex.: "dup#1","dup#2"...)
    ordem_pai = models.ForeignKey(
        'self',  # Referencia a própria tabela
        on_delete=models.SET_NULL,  # Define como `NULL` se a ordem pai for excluída
        null=True,  # Permite valores nulos para ordens que não têm "pai"
        blank=True,
        related_name='ordens_filhas',  # Permite acessar as duplicatas a partir da ordem original
        verbose_name='Ordem Pai'
    )
    duplicada = models.BooleanField(default=False) # Opção para ordens duplicadas

    #Campos para apontamento de montagem e pintura
    data_carga = models.DateField(null=True, blank=True)
    cor = models.CharField(max_length=50, blank=True, null=True) # Cinza, Vermelho, Amarelo...

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ordem', 'maquina'], name='unique_ordem_processo')
        ]

    def save(self, *args, **kwargs):
        
        if self.grupo_maquina == 'montagem' and self.data_carga:
            self.data_programacao = self.data_carga - timedelta(days=3)

            # Se a data_programacao cair num sábado (5) ou domingo (6), ajustar para sexta-feira
            while self.data_programacao.weekday() in [5, 6]:  # 5 = Sábado, 6 = Domingo
                self.data_programacao -= timedelta(days=1)  # Retrocede até sexta

        elif self.grupo_maquina == 'pintura' and self.data_carga:
            self.data_programacao = self.data_carga - timedelta(days=1)

            # Se a data_programacao cair num sábado (5) ou domingo (6), ajustar para sexta-feira
            while self.data_programacao.weekday() in [5, 6]:  # 5 = Sábado, 6 = Domingo
                self.data_programacao -= timedelta(days=1)  # Retrocede até sexta

        if not self.pk and self.duplicada:
            # Gera uma identificação única para a duplicata
            if self.ordem_pai:
                duplicatas_existentes = Ordem.objects.filter(ordem_pai=self.ordem_pai).count()
                self.ordem_duplicada = f"dup#{self.ordem_pai.ordem}.{duplicatas_existentes + 1}"
            else:
                self.ordem_duplicada = "dup#1"  # Caso não tenha um pai definido (fallback)

        # Incrementa automaticamente apenas para os grupos diferentes de "Laser" e "Plasma"
        elif not self.pk and self.grupo_maquina not in ['laser_1','laser_2','plasma']:
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
    aproveitamento=models.FloatField(null=True, blank=True)
    tipo_chapa = models.CharField(max_length=20, choices=TIPO_CHAPA_CHOICES, null=True, blank=True)
    retalho = models.BooleanField(default=False)
    nova_mp = models.ForeignKey(Mp, on_delete=models.CASCADE, related_name='nova_mp', blank=True, null=True) # caso o usuario opte por mudar ao finalizar a ordem

class OrdemProcesso(models.Model):
    
    ordem = models.ForeignKey(Ordem, on_delete=models.CASCADE, related_name='processos')
    status = models.CharField(max_length=20, choices=STATUS_ANDAMENTO_CHOICES)
    data_inicio = models.DateTimeField(default=now)  # Armazena quando o status foi definido
    data_fim = models.DateTimeField(null=True, blank=True)  # Armazena quando o status foi finalizado
    motivo_interrupcao = models.ForeignKey(MotivoInterrupcao, on_delete=models.CASCADE, null=True, blank=True)
    maquina = models.ForeignKey(Maquina, related_name='processo_maquina', on_delete=models.CASCADE, null=True, blank=True)

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

class MaquinaParada(models.Model):

    maquina = maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='maquina_maquina_parada', blank=True, null=True)
    data_inicio = models.DateTimeField(default=now)
    data_fim = models.DateTimeField(null=True, blank=True)
    motivo = models.ForeignKey(MotivoMaquinaParada, on_delete=models.CASCADE, null=True, blank=True)

class RotaAcesso(models.Model):

    TIPO_ROTA_CHOICES=(('api','Api'),('template','Template'))

    APP_CHOICES = [
        ('core', 'Core'),
        ('users', 'Users'),
        ('serra', 'Serra'),
        ('estamparia', 'Estamparia'),
        ('montagem', 'Montagem'),
        ('pintura', 'Pintura'),
        ('prod_especiais', 'Prod Especiais'),
        ('corte', 'Corte'),
        ('usinagem', 'Usinagem'),
        ('cargas', 'Cargas'),
        ('inspecao', 'Inspeção'),
    ]

    nome=models.CharField(max_length=50,unique=True) # exemplo: serra/historico
    descricao=models.CharField(max_length=100) # exemplo: hstorico de serra
    tipo_rota=models.CharField(max_length=10, choices=TIPO_ROTA_CHOICES) 
    app=models.CharField(max_length=50, choices=APP_CHOICES)

    def __str__(self):
        return self.nome

class Profile(models.Model):
    ACESSO_CHOICES = [
        ('operador', 'Operador'),
        ('supervisor', 'Supervisor'),
        ('pcp', 'PCP'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tipo_acesso = models.CharField(max_length=20, choices=ACESSO_CHOICES)
    
    permissoes = models.ManyToManyField(RotaAcesso, blank=True)  # Permissões específicas para rotas

    def __str__(self):
        return f"{self.user.username} - {self.tipo_acesso}"
    
    def tem_acesso(self, rota_nome):
        """ Verifica se o usuário tem acesso a uma determinada rota """
        return self.permissoes.filter(nome=rota_nome).exists()

class Versao(models.Model):
    
    TIPO_CHOICES = (
        ('bug', 'Bug'),
        ('funcionalidade', 'Funcionalidade'),
        ('implementacao', 'Implementação'),
    )
    
    numero = models.CharField(max_length=10, unique=True, blank=True)
    data_lancamento = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()

    def save(self, *args, **kwargs):
        if not self.pk:  # Só gera uma nova versão se for um novo registro
            ultima_versao = Versao.objects.order_by('-data_lancamento').first()

            if ultima_versao:
                partes = [int(x) for x in ultima_versao.numero.split('.')]  # Divide a versão em [X, Y, Z]
            else:
                partes = [0, 0, 0]  # Se não houver versões, inicia com "1.0.0"

            # Define o incremento com base no tipo de alteração
            if self.tipo == 'bug':
                partes[2] += 1  # Ex: 1.0.1 → 1.0.2
            elif self.tipo == 'funcionalidade':
                partes[1] += 1  # Ex: 1.1.0 → 1.2.0
                partes[2] = 0  # Reinicia o último número
            elif self.tipo == 'implementacao':
                partes[0] += 1  # Ex: 2.0.0 → 3.0.0
                partes[1] = 0
                partes[2] = 0  # Reinicia os números menores

            self.numero = f"{partes[0]}.{partes[1]}.{partes[2]}"  # Monta a nova versão

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Versão {self.numero}"

class SolicitacaoPeca(models.Model):

    peca=models.ForeignKey(Pecas, on_delete=models.CASCADE, related_name='peca_solicitacao_peca')
    qtd_solicitada=models.FloatField(default=1)
    localizacao_solicitante=models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='localizacao_solicitacao_peca')
    mais_informacoes=models.TextField(blank=True, null=True)
    data_solicitacao=models.DateField(auto_now_add=True)
    data_carga=models.DateField(blank=True, null=True)
    

    def __str__(self):
        return f"{self.peca} - {self.setor_solicitante}"