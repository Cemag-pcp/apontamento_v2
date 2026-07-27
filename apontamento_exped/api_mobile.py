"""
API autenticada por token (DRF), consumida pelo app mobile. Todas as
views aqui sao wrappers finos sobre apontamento_exped/services.py - a
mesma logica de negocio usada pelas views classicas em views.py.
"""
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Carga, ImagemPacote, ItemPacote, Pacote
from .serializers import (
    AtualizarQuantidadeItemSerializer,
    ConfirmarPacoteSerializer,
    CriarPacoteSerializer,
    FornecedorItemInputSerializer,
    LoginSerializer,
    MoverItemSerializer,
    UploadFotoSerializer,
)
from .services import (
    FotoObrigatoriaError,
    PacoteValidationError,
    atualizar_quantidade_item_service,
    confirmar_pacote_service,
    criar_ou_atualizar_pacote,
    deletar_pacote_service,
    detalhar_pacotes_da_carga,
    duplicar_pacote_service,
    excluir_carga_service,
    excluir_foto_pacote,
    excluir_item_pacote_service,
    listar_cargas_ativas,
    listar_fotos_pacote,
    listar_pendencias_carga,
    mover_item_pacote,
    salvar_foto_pacote,
    salvar_fornecedores_carga,
)


def _serializar_usuario(user):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'username': user.username,
        'nome_completo': user.get_full_name() or user.username,
        'tipo_acesso': getattr(profile, 'tipo_acesso', None),
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if not user:
            return Response({'erro': 'Usuário ou senha inválidos.'}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': _serializar_usuario(user)})


class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(_serializar_usuario(request.user))


class CargasListView(APIView):
    def get(self, request):
        return Response(listar_cargas_ativas())


class ExcluirCargaView(APIView):
    def delete(self, request, carga_id):
        profile = getattr(request.user, 'profile', None)
        if getattr(profile, 'tipo_acesso', None) != 'pcp':
            return Response(
                {'erro': 'Acesso negado: apenas PCP pode excluir carregamentos.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        carga = get_object_or_404(Carga, id=carga_id)
        excluir_carga_service(carga)
        return Response({'mensagem': 'Carregamento excluído com sucesso.'})


class PacotesCargaView(APIView):
    def get(self, request, carga_id):
        carga = get_object_or_404(Carga, id=carga_id)
        return Response(detalhar_pacotes_da_carga(carga))


class PendenciasCargaView(APIView):
    def get(self, request, carga_id):
        return Response(listar_pendencias_carga(carga_id))


class FotosPacoteView(APIView):
    def get(self, request, pacote_id):
        return Response({'fotos': listar_fotos_pacote(pacote_id)})


class UploadFotoView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pacote_id):
        serializer = UploadFotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pacote = get_object_or_404(Pacote, id=pacote_id)
        resultado = salvar_foto_pacote(pacote, serializer.validated_data['foto'])
        return Response(resultado, status=status.HTTP_201_CREATED)


class ExcluirFotoView(APIView):
    def delete(self, request, foto_id):
        imagem = get_object_or_404(ImagemPacote, id=foto_id)
        excluir_foto_pacote(imagem)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeletarPacoteView(APIView):
    def delete(self, request, pacote_id):
        pacote = get_object_or_404(Pacote.objects.select_related('carga'), id=pacote_id)
        try:
            resultado = deletar_pacote_service(pacote)
        except PacoteValidationError as exc:
            return Response({'erro': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado)


class DuplicarPacoteView(APIView):
    def post(self, request, pacote_id):
        pacote = get_object_or_404(Pacote.objects.select_related('carga'), id=pacote_id)
        try:
            resultado = duplicar_pacote_service(pacote)
        except PacoteValidationError as exc:
            return Response({'erro': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado, status=status.HTTP_201_CREATED)


class CriarPacoteView(APIView):
    def post(self, request, carga_id):
        serializer = CriarPacoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        carga = get_object_or_404(Carga, id=carga_id)
        try:
            resultado = criar_ou_atualizar_pacote(
                carga,
                nome_pacote=dados.get('nome_pacote'),
                pacote_existente_id=dados.get('pacote_existente_id'),
                itens=dados.get('itens', []),
                itens_fora_planejado=dados.get('itens_fora_planejado', []),
            )
        except PacoteValidationError as exc:
            return Response({'erro': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado, status=status.HTTP_201_CREATED)


class AtualizarQuantidadeItemView(APIView):
    def post(self, request, item_id):
        serializer = AtualizarQuantidadeItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = get_object_or_404(
            ItemPacote.objects.select_related('codigo', 'pacote__carga'), id=item_id
        )
        try:
            resultado = atualizar_quantidade_item_service(item, serializer.validated_data['quantidade'])
        except PacoteValidationError as exc:
            return Response({'erro': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado)


class ExcluirItemPacoteView(APIView):
    def delete(self, request, item_id):
        item = get_object_or_404(
            ItemPacote.objects.select_related('codigo', 'pacote__carga'), id=item_id
        )
        try:
            resultado = excluir_item_pacote_service(item)
        except PacoteValidationError as exc:
            return Response({'erro': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado)


class MoverItemView(APIView):
    def post(self, request, item_id):
        serializer = MoverItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = get_object_or_404(ItemPacote, id=item_id)
        pacote_destino = get_object_or_404(Pacote, id=serializer.validated_data['pacote_destino_id'])
        resultado = mover_item_pacote(item, pacote_destino)
        return Response(resultado)


class SalvarFornecedoresView(APIView):
    def post(self, request, carga_id):
        serializer = FornecedorItemInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        carga = get_object_or_404(Carga, id=carga_id)
        resultado = salvar_fornecedores_carga(carga, serializer.validated_data)
        return Response(resultado)


class ConfirmarPacoteView(APIView):
    def post(self, request, pacote_id):
        serializer = ConfirmarPacoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pacote = get_object_or_404(Pacote, id=pacote_id)
        try:
            resultado = confirmar_pacote_service(pacote, serializer.validated_data.get('observacao'))
        except FotoObrigatoriaError as exc:
            return Response({'erro': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(resultado)
