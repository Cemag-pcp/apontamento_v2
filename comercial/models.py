from django.contrib.auth.models import User
from django.db import models


class ConferenciaPedido(models.Model):
    chave_pedido = models.CharField(max_length=100)
    deal_id = models.CharField(max_length=100)
    quote_id = models.CharField(max_length=100)
    data_criacao = models.CharField(max_length=100, blank=True)
    contato = models.CharField(max_length=255, blank=True)
    observacao = models.TextField(blank=True)
    itens = models.JSONField(default=list)
    conferido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='conferencias_pedido',
    )
    conferido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['chave_pedido', 'deal_id', 'quote_id'],
                name='unique_conferencia_pedido',
            )
        ]
        ordering = ['-conferido_em']

    def __str__(self):
        return f'{self.chave_pedido} / {self.quote_id}'


class PendenciaImportacaoPlanilha(models.Model):
    ped_ufpessoaop_regiao_nome = models.CharField(
        max_length=100,
        db_column='PED_UFPESSOAOP.REGIAO.NOME',
    )
    ped_pessoa_uf_codigo = models.CharField(
        max_length=10,
        db_column='PED_PESSOA.UF.CODIGO',
    )
    ped_observacao = models.TextField(
        blank=True,
        db_column='PED_OBSERVACAO',
    )
    ped_pessoa_localidade_codigo = models.CharField(
        max_length=100,
        db_column='PED_PESSOA.LOCALIDADE.CODIGO',
    )
    ped_chcriacao = models.CharField(
        max_length=50,
        db_column='PED_CHCRIACAO',
    )
    ped_emissao = models.DateField(
        db_column='PED_EMISSAO',
    )
    ped_previsaoemissaodoc = models.DateField(
        db_column='PED_PREVISAOEMISSAODOC',
    )
    ped_programaca = models.DateField(
        db_column='PED_PROGRAMACA',
    )
    ped_classe_nome = models.CharField(
        max_length=150,
        db_column='PED_CLASSE.NOME',
    )
    ped_pessoa_codigo = models.CharField(
        max_length=150,
        db_column='PED_PESSOA.CODIGO',
    )
    ped_recurso_codigo = models.CharField(
        max_length=100,
        db_column='PED_RECURSO.CODIGO',
    )
    ped_recurso_nome = models.TextField(
        db_column='PED_RECURSO.NOME',
    )
    ped_recurso_classe_nome = models.CharField(
        max_length=150,
        db_column='PED_RECURSO.CLASSE.NOME',
    )
    ped_numeroserie = models.CharField(
        max_length=100,
        blank=True,
        db_column='PED_NUMEROSERIE',
    )
    ped_nucleo_codigo = models.CharField(
        max_length=100,
        db_column='PED_NUCLEO.CODIGO',
    )
    ped_quantidade = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        db_column='PED_QUANTIDADE',
    )
    ped_unitario = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        db_column='PED_UNITARIO',
    )
    ped_total = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        db_column='PED_TOTAL',
    )
    ped_recurso_descricaogenerica = models.CharField(
        max_length=150,
        db_column='PED_RECURSO.DESCRICAOGENERICA',
    )
    ped_representa_codigo = models.CharField(
        max_length=150,
        db_column='PED_REPRESENTA.CODIGO',
    )
    ped_idnegociacao = models.CharField(
        max_length=50,
        db_column='PED_IDNEGOCIACAO',
    )

    class Meta:
        db_table = 'comercial_pendencia_importacao_planilha'
        verbose_name = 'Pendência para Importação na Planilha'
        verbose_name_plural = 'Pendências para Importação na Planilha'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'ped_idnegociacao',
                    'ped_chcriacao',
                    'ped_recurso_codigo',
                    'ped_numeroserie',
                ],
                name='unique_pend_import_planilha_item',
            )
        ]

    def __str__(self):
        return f'{self.ped_chcriacao} / {self.ped_recurso_codigo}'
