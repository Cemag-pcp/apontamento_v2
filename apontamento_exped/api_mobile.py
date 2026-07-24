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

from .models import Carga, Pacote
from .serializers import (
    ConfirmarPacoteSerializer,
    CriarPacoteSerializer,
    LoginSerializer,
    UploadFotoSerializer,
)
from .services import (
    FotoObrigatoriaError,
    PacoteValidationError,
    confirmar_pacote_service,
    criar_ou_atualizar_pacote,
    detalhar_pacotes_da_carga,
    listar_cargas_ativas,
    listar_fotos_pacote,
    listar_pendencias_carga,
    salvar_foto_pacote,
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
