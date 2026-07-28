from django.conf import settings
from django.db import models


class MensagemChatAssistente(models.Model):
    ROLE_CHOICES = [
        ('user', 'Usuário'),
        ('assistant', 'Assistente'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mensagens_chat_assistente',
    )
    sessao_id = models.CharField(max_length=36)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    conteudo = models.TextField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criada_em']
        indexes = [
            models.Index(fields=['usuario', 'sessao_id', 'criada_em']),
        ]

    def __str__(self):
        return f'{self.usuario_id} [{self.role}] {self.conteudo[:40]}'
