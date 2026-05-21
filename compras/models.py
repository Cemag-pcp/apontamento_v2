from django.db import models


class AnaliseIA(models.Model):
    codigo = models.CharField(max_length=100, db_index=True)
    dados_hash = models.CharField(max_length=64)
    analise = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        indexes = [models.Index(fields=['codigo', 'dados_hash'])]
