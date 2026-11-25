import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models.functions import Lower


class Inventario(models.Model):
    """Um inventário (ex.: "Inventário 2026"), no qual o usuário "entra"
    para trabalhar."""

    STATUS_CHOICES = [
        ('aberto', 'Aberto'),
        ('finalizado', 'Finalizado'),
    ]

    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberto')
    # Chave do link público da contagem (/inventario/contagem/<token>/),
    # que funciona sem login enquanto o inventário estiver aberto.
    token_contagem = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventarios_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Inventário'
        verbose_name_plural = 'Inventários'

    @property
    def aberto(self):
        return self.status == 'aberto'

    def __str__(self):
        return self.nome


class CadastroInventario(models.Model):
    """Setor + célula + responsável de um inventário (ex.: Montagem / Chassi /
    3123 - José). A combinação não se repete no mesmo inventário, sem
    diferenciar maiúsculas (os espaços extras são tirados ao salvar).

    Responsável vazio = pendente: setor/célula criados pela importação da
    lista de contagem, esperando alguém definir o responsável."""

    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE, related_name='cadastros')
    setor = models.CharField(max_length=100)
    celula = models.CharField(max_length=100)
    responsavel = models.CharField(max_length=150, blank=True, default='')
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cadastros_inventario_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['setor', 'celula', 'responsavel']
        verbose_name = 'Cadastro do inventário'
        verbose_name_plural = 'Cadastros do inventário'
        constraints = [
            models.UniqueConstraint(
                'inventario', Lower('setor'), Lower('celula'), Lower('responsavel'),
                name='inventario_cadastro_setor_celula_responsavel_unico',
            ),
        ]

    @property
    def pendente(self):
        return not self.responsavel

    def __str__(self):
        return f'{self.setor} / {self.celula} / {self.responsavel or "(pendente)"}'


class ItemContagem(models.Model):
    """Linha da lista de contagem (Setor | Célula | Código | Descrição),
    importada por planilha. É onde as quantidades encontradas no inventário
    serão lançadas. O mesmo código não se repete na mesma célula."""

    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE, related_name='itens_contagem')
    setor = models.CharField(max_length=100)
    celula = models.CharField(max_length=100)
    codigo = models.CharField(max_length=60)
    descricao = models.CharField(max_length=255, blank=True, default='')
    # Contagem feita pelo link público: só a quantidade e o horário
    # (gravado com fuso; exibido no horário de Brasília). Recontar substitui.
    quantidade = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    contado_em = models.DateTimeField(null=True, blank=True)
    # Peça achada na contagem que não estava na planilha (ex.: lote no pátio),
    # lançada pelo próprio link: o operador informa código, quantidade e onde
    # achou (observação). Fica sem célula, e cada lote é uma linha própria.
    fora_da_lista = models.BooleanField(default=False)
    # Recontagem: habilitada pelo painel para itens já contados. A primeira
    # contagem fica guardada; a recontagem vai nestes campos próprios.
    recontagem_habilitada = models.BooleanField(default=False)
    recontagem = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    recontado_em = models.DateTimeField(null=True, blank=True)
    observacao = models.CharField(max_length=255, blank=True, default='')
    # foto opcional do lote fora da lista (ajuda a identificar a peça)
    foto = models.ImageField(upload_to='inventario_fora_da_lista/', null=True, blank=True)
    importado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_contagem_importados',
    )
    importado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['setor', 'celula', 'codigo']
        verbose_name = 'Item da contagem'
        verbose_name_plural = 'Itens da contagem'
        constraints = [
            # vale só para a lista importada; fora da lista pode ter vários
            # lotes do mesmo código
            models.UniqueConstraint(
                'inventario', Lower('setor'), Lower('celula'), Lower('codigo'),
                condition=models.Q(fora_da_lista=False),
                name='inventario_item_setor_celula_codigo_unico',
            ),
        ]

    def __str__(self):
        return f'{self.setor} / {self.celula} / {self.codigo}'
