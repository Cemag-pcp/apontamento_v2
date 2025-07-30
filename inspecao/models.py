from django.db import models
from core.models import Profile
from cadastro.models import PecasEstanqueidade

class Inspecao(models.Model):

    data_inspecao = models.DateTimeField(auto_now_add=True)

    # Chaves estrangeiras opcionais para cada setor
    pecas_ordem_pintura = models.ForeignKey(
        "apontamento_pintura.PecasOrdem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    pecas_ordem_montagem = models.ForeignKey(
        "apontamento_montagem.PecasOrdem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    pecas_ordem_estamparia = models.ForeignKey(
        "apontamento_estamparia.PecasOrdem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    pecas_ordem_serra = models.ForeignKey(
        "apontamento_serra.PecasOrdem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    pecas_ordem_usinagem = models.ForeignKey(
        "apontamento_usinagem.PecasOrdem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self):

        if self.pecas_ordem_pintura:
            setor_inspecao = f"Pintura - {self.pecas_ordem_pintura.id}"
        elif self.pecas_ordem_montagem:
            setor_inspecao = f"Montagem - {self.pecas_ordem_montagem.id}"
        elif self.pecas_ordem_serra:
            setor_inspecao = f"Serra - {self.pecas_ordem_serra.id}"
        elif self.pecas_ordem_usinagem:
            setor_inspecao = f"Usinagem - {self.pecas_ordem_usinagem.id}"
        else:
            setor_inspecao = f"Estamparia - {self.pecas_ordem_estamparia.id}"

        return f"Inspeção {self.id} - {setor_inspecao}"

class DadosExecucaoInspecao(models.Model):

    inspecao = models.ForeignKey(
        Inspecao, on_delete=models.CASCADE, null=False, blank=False
    )
    inspetor = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True
    )
    data_execucao = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    num_execucao = models.IntegerField(null=True, blank=True)
    conformidade = models.IntegerField(null=False, blank=False)
    nao_conformidade = models.IntegerField(null=False, blank=False)
    observacao = models.CharField(max_length=150, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Verifica se o objeto já existe no banco de dados
        if self.pk is None:
            # Se não existe, busca o último num_execucao para o mesmo inspecao_estanqueidade
            ultima_execucao = (
                DadosExecucaoInspecao.objects.filter(inspecao=self.inspecao)
                .order_by("-num_execucao")
                .first()
            )

            # Se existir uma execução anterior, incrementa o num_execucao
            if ultima_execucao:
                self.num_execucao = ultima_execucao.num_execucao + 1
            else:
                # Se não existir, começa com 0
                self.num_execucao = 0

        # Chama o método save da superclasse para salvar o objeto
        super(DadosExecucaoInspecao, self).save(*args, **kwargs)

class Reinspecao(models.Model):

    inspecao = models.ForeignKey(
        Inspecao, on_delete=models.CASCADE, null=False, blank=False
    )
    data_reinspecao = models.DateTimeField(auto_now_add=True)
    reinspecionado = models.BooleanField(default=False)

class Causas(models.Model):

    SETOR_CHOICES = (
        ("pintura", "Pintura"),
        ("montagem", "Montagem"),
        ("estamparia", "Estamparia"),
        ("serra-usinagem", "Serra e Usinagem"),
        ("tubos cilindros", "Tubos e Cilindros"),
        ("tanque", "Tanque"),
    )

    nome = models.CharField(max_length=40, null=False, blank=False)
    setor = models.CharField(
        max_length=40, choices=SETOR_CHOICES, null=False, blank=False
    )

    def __str__(self):
        return f"{self.nome} - setor {self.setor}"

    class Meta:
        verbose_name = "Causa"


class CausasNaoConformidade(models.Model):

    dados_execucao = models.ForeignKey(
        DadosExecucaoInspecao, on_delete=models.CASCADE, null=False, blank=False
    )
    causa = models.ManyToManyField(
        Causas, related_name="causas_nao_conformidade", blank=True
    )
    quantidade = models.IntegerField(null=False, blank=False)


class ArquivoCausa(models.Model):
    causa_nao_conformidade = models.ForeignKey(
        CausasNaoConformidade, on_delete=models.CASCADE, related_name="arquivos"
    )
    arquivo = models.ImageField(
        upload_to="causas_nao_conformidade/", null=True, blank=True
    )


#### Inspecao Estanqueidade ####


class InspecaoEstanqueidade(models.Model):

    data_inspecao = models.DateTimeField(null=False, blank=False)
    peca = models.ForeignKey(
        PecasEstanqueidade, on_delete=models.CASCADE, null=False, blank=False
    )
    data_carga = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.peca} - {self.data_inspecao}"


class DadosExecucaoInspecaoEstanqueidade(models.Model):

    inspecao_estanqueidade = models.ForeignKey(
        InspecaoEstanqueidade, on_delete=models.CASCADE, null=False, blank=False
    )
    inspetor = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True
    )
    num_execucao = models.IntegerField(null=True, blank=True)
    data_exec = models.DateTimeField()

    def save(self, *args, **kwargs):
        # Verifica se o objeto já existe no banco de dados
        if self.pk is None:
            # Se não existe, busca o último num_execucao para o mesmo inspecao_estanqueidade
            ultima_execucao = (
                DadosExecucaoInspecaoEstanqueidade.objects.filter(
                    inspecao_estanqueidade=self.inspecao_estanqueidade
                )
                .order_by("-num_execucao")
                .first()
            )

            # Se existir uma execução anterior, incrementa o num_execucao
            if ultima_execucao:
                self.num_execucao = ultima_execucao.num_execucao + 1
            else:
                # Se não existir, começa com 0
                self.num_execucao = 0

        # Chama o método save da superclasse para salvar o objeto
        super(DadosExecucaoInspecaoEstanqueidade, self).save(*args, **kwargs)


class ReinspecaoEstanqueidade(models.Model):

    inspecao = models.ForeignKey(
        InspecaoEstanqueidade,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    data_reinsp = models.DateTimeField(auto_now_add=True)
    reinspecionado = models.BooleanField(default=False)


class DetalhesPressaoTanque(models.Model):

    TIPO_TESTE = (
        ("ctpi", "Corpo do tanque parte inferior"),
        ("ctl", "Corpo do tanque + longarinas"),
        ("ct", "Corpo do tanque"),
        ("ctc", "Corpo do tanque + chassi"),
    )

    dados_exec_inspecao = models.ForeignKey(
        DadosExecucaoInspecaoEstanqueidade,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    pressao_inicial = models.FloatField(null=False, blank=False)
    pressao_final = models.FloatField(null=False, blank=False)
    nao_conformidade = models.BooleanField(default=False)
    tipo_teste = models.CharField(
        max_length=5, choices=TIPO_TESTE, null=False, blank=False
    )
    tempo_execucao = models.TimeField(null=False, blank=False)


class InfoAdicionaisExecTubosCilindros(models.Model):

    dados_exec_inspecao = models.ForeignKey(
        DadosExecucaoInspecaoEstanqueidade,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    nao_conformidade = models.IntegerField(null=False, blank=False)
    nao_conformidade_refugo = models.IntegerField(null=False, blank=False)
    qtd_inspecionada = models.IntegerField(null=False, blank=False)
    observacao = models.CharField(max_length=100, null=True, blank=True)
    ficha = models.ImageField(upload_to="ficha_tubos_cilindros/", null=True, blank=True)


class CausasNaoConformidadeEstanqueidade(models.Model):

    info_tubos_cilindros = models.ForeignKey(
        InfoAdicionaisExecTubosCilindros,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    causa = models.ManyToManyField(
        Causas, related_name="causas_nao_conformidade_estanqueidade", blank=True
    )
    quantidade = models.IntegerField(null=False, blank=False)

class ArquivoCausaEstanqueidade(models.Model):
    causa_nao_conformidade = models.ForeignKey(
        CausasNaoConformidadeEstanqueidade,
        on_delete=models.CASCADE,
        related_name="arquivos_estanqueidade",
    )
    arquivos = models.ImageField(
        upload_to="causas_nao_conformidade_estanqueidade/", null=True, blank=True
    )
