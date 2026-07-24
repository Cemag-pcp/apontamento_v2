from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ConfirmarPacoteSerializer(serializers.Serializer):
    observacao = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class UploadFotoSerializer(serializers.Serializer):
    foto = serializers.ImageField()
