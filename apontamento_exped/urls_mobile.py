from django.urls import path

from . import api_mobile

app_name = 'expedicao_mobile'

urlpatterns = [
    path('login/', api_mobile.LoginView.as_view(), name='login'),
    path('logout/', api_mobile.LogoutView.as_view(), name='logout'),
    path('me/', api_mobile.MeView.as_view(), name='me'),
    path('cargas/', api_mobile.CargasListView.as_view(), name='cargas'),
    path('cargas/<int:carga_id>/pacotes/', api_mobile.PacotesCargaView.as_view(), name='pacotes_carga'),
    path('cargas/<int:carga_id>/pendencias/', api_mobile.PendenciasCargaView.as_view(), name='pendencias_carga'),
    path('cargas/<int:carga_id>/pacotes/criar/', api_mobile.CriarPacoteView.as_view(), name='criar_pacote'),
    path('cargas/<int:carga_id>/fornecedores/', api_mobile.SalvarFornecedoresView.as_view(), name='salvar_fornecedores'),
    path('pacotes/<int:pacote_id>/fotos/', api_mobile.FotosPacoteView.as_view(), name='fotos_pacote'),
    path('pacotes/<int:pacote_id>/foto/', api_mobile.UploadFotoView.as_view(), name='upload_foto'),
    path('fotos/<int:foto_id>/', api_mobile.ExcluirFotoView.as_view(), name='excluir_foto'),
    path('pacotes/<int:pacote_id>/confirmar/', api_mobile.ConfirmarPacoteView.as_view(), name='confirmar_pacote'),
    path('pacotes/<int:pacote_id>/duplicar/', api_mobile.DuplicarPacoteView.as_view(), name='duplicar_pacote'),
    path('pacotes/<int:pacote_id>/', api_mobile.DeletarPacoteView.as_view(), name='deletar_pacote'),
]
