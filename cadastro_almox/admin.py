from django.contrib import admin

from .models import *

admin.site.register(Cc)
admin.site.register(DepositoDestino,DepositoDestinoAdmin)
admin.site.register(Funcionario,FuncionarioAdmin)
admin.site.register(ItensSolicitacao,ItensSolicitacaoAdmin)
admin.site.register(ItensTransferencia,ItensTransferenciaAdmin)
admin.site.register(OperadorAlmox)
admin.site.register(ClasseRequisicao)
