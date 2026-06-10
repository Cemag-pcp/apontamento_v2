from django.db import models
from django.contrib.auth.models import User
from cadastro.models import Setor


class Report(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_reuniao')
    texto = models.TextField()
    data = models.DateField()
    setor = models.ForeignKey(
        Setor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_reuniao',
    )
    concluido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'

    def __str__(self):
        return f"{self.usuario.username} - {self.data}"
