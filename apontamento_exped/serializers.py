from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ConfirmarPacoteSerializer(serializers.Serializer):
    observacao = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class UploadFotoSerializer(serializers.Serializer):
    foto = serializers.ImageField()


class ItemPacoteInputSerializer(serializers.Serializer):
    pendencia_id = serializers.IntegerField()
    quantidade = serializers.IntegerField()


class ItemForaPlanejadoInputSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    descricao = serializers.CharField()
    quantidade = serializers.IntegerField()


class CriarPacoteSerializer(serializers.Serializer):
    nome_pacote = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pacote_existente_id = serializers.IntegerField(required=False, allow_null=True)
    itens = ItemPacoteInputSerializer(many=True, required=False)
    itens_fora_planejado = ItemForaPlanejadoInputSerializer(many=True, required=False)
