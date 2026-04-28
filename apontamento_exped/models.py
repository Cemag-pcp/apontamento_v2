from django.db import models

from core.models import Profile

class Carga(models.Model):
    nome = models.CharField(max_length=100)  # Ex: Carga 123
    carga = models.CharField(max_length=100) # Ex.: Carga 01, Carga 02
    data_carga = models.DateField(null=True, blank=True)  # Data da carga
    cliente = models.CharField(max_length=100)  # Ex: Cliente X
    obs_pacote = models.TextField(blank=True)  # Observações gerais sobre o pacote
    stage = models.CharField(max_length=50, choices=[('planejamento', 'Planejamento'), ('apontamento', 'Apontamento'), ('verificacao', 'Verificação'), ('despachado','Despachado')], default='planejamento')

    responsavel_criacao = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_despachado = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[('pendente', 'Pendente'), ('ok', 'Confirmado'), ('erro', 'Erro identificado')], default='pendente')

    def __str__(self):
        return self.nome

class CarretaCarga(models.Model):
    carga = models.ForeignKey(Carga, related_name='carretas', on_delete=models.CASCADE)
    carreta = models.CharField(max_length=100)  # Ex: VM1234
    quantidade = models.PositiveIntegerField()
    cor = models.CharField(max_length=50)  # Ex: vermelho, azul, etc.

    def __str__(self):
        return f"{self.recurso} - {self.quantidade}"

class Pacote(models.Model):
    nome = models.CharField(max_length=100)  # Ex: CLIENTE_X_001
    carga = models.ForeignKey(Carga, related_name='pacotes', on_delete=models.CASCADE)
    criado_por = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    # ETAPA DA EXPEDIÇÃO 

    confirmado_por_expedicao = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmou_pacotes_expedicao')
    data_confirmacao_expedicao = models.DateTimeField(null=True, blank=True)
    status_confirmacao_expedicao = models.CharField(max_length=50, choices=[('pendente', 'Pendente'), ('ok', 'Confirmado'), ('erro', 'Erro identificado')], default='pendente')
    obs_expedicao = models.TextField(blank=True)

    # ETAPA DA QUALIDADE

    confirmado_por_qualidade = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmou_pacotes_qualidade')
    data_confirmacao_qualidade = models.DateTimeField(null=True, blank=True)
    status_confirmacao_qualidade = models.CharField(max_length=50, choices=[('pendente', 'Pendente'), ('ok', 'Confirmado'), ('erro', 'Erro identificado')], default='pendente')
    obs_qualidade = models.TextField(blank=True) 

    def __str__(self):
        return self.nome

class VerificacaoPacote(models.Model):
    pacote = models.OneToOneField(Pacote, on_delete=models.CASCADE, related_name='verificacao')
    verificado_por = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    data_verificacao = models.DateTimeField(auto_now_add=True)
    tudo_correto = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)  # Caso algo esteja errado, detalha aqui

    def __str__(self):
        return f"Verificação do {self.pacote.numero}"

class ImagemPacote(models.Model):

    pacote = models.ForeignKey(Pacote, on_delete=models.CASCADE, related_name='pacote_imagem')
    arquivo = models.ImageField(
        upload_to="imagem_pacote/", null=True, blank=True
    )
    stage = models.CharField(max_length=50, choices=[('verificacao', 'Verificação'), ('despachado','Despachado')])

class PendenciasPacote(models.Model):

    """
    Gerado a partir do momento em que o usuário cria o carregamento

    Busca a informação das peças e quantidades na planilha BASE GERAL
    """

    carreta_carga = models.ForeignKey(CarretaCarga, related_name='carreta_carga', on_delete=models.CASCADE)
    codigo = models.CharField(max_length=255, blank=True, null=True)    
    descricao = models.CharField(max_length=255, blank=True, null=True)
    qt_necessaria = models.IntegerField()
    
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.codigo}"

class FornecedorItemCarga(models.Model):
    """
    Armazena o fornecedor por código único de peça especial (Pneu, Cilindro, Roda)
    em uma carga. Um registro por combinação (carga, tipo, codigo).
    Obrigatório para avançar da verificação.
    """
    carga = models.ForeignKey(Carga, on_delete=models.CASCADE, related_name='fornecedores_itens')
    tipo = models.CharField(max_length=50)   # 'Pneu', 'Cilindro', 'Roda'
    codigo = models.CharField(max_length=255)  # código da peça
    fornecedor = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('carga', 'tipo', 'codigo')

    def __str__(self):
        return f"Fornecedor {self.tipo} ({self.codigo}) - Carga {self.carga_id}"

class ItemPacote(models.Model):

    """
    Gerado quando o usuario cria o pacote.
    """

    pacote = models.ForeignKey(Pacote, related_name='itens', on_delete=models.CASCADE)
    codigo = models.ForeignKey(PendenciasPacote, related_name='codigo_item_pacote', on_delete=models.CASCADE, null=True, blank=True)
    codigo_informado = models.CharField(max_length=255, blank=True, null=True)
    descricao_informada = models.CharField(max_length=255, blank=True, null=True)
    fora_planejado = models.BooleanField(default=False)
    quantidade = models.PositiveIntegerField()

    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.codigo_id:
            return f"{self.codigo}"
        return f"{self.codigo_informado or 'Item avulso'}"
