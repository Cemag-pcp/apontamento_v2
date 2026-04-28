from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cargas.models import CargaLiberada, CargaLiberadaItem, CargaLiberadaVersao


class ExpedicaoLiberacaoTests(TestCase):
    @staticmethod
    def _date(value):
        from datetime import date

        return date.fromisoformat(value)

    def setUp(self):
        self.user = User.objects.create_user(username="exped_teste", password="123456")

    def _criar_liberacao(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="034550VM",
            quantidade=2,
            presente_no_carreta="✅",
            cliente="Cliente A",
            cliente_codigo="CLI001",
            numero_serie="SERIE-01",
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="034550VM",
            quantidade=1,
            presente_no_carreta="✅",
            cliente="Cliente A",
            cliente_codigo="CLI001",
            numero_serie="SERIE-02",
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="078900AN",
            quantidade=3,
            presente_no_carreta="❌",
            cliente="Cliente B",
            cliente_codigo="CLI002",
            numero_serie="SERIE-03",
        )
        return carga, versao

    def test_cargas_disponiveis_vem_da_base_liberada(self):
        self._criar_liberacao()

        response = self.client.get(
            reverse("expedicao:cargas"),
            {"data_carga": "2026-04-27"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Carga 04"])

    def test_clientes_disponiveis_vem_da_base_liberada(self):
        self._criar_liberacao()

        response = self.client.get(
            reverse("expedicao:clientes"),
            {"data_carga": "2026-04-27", "carga": "Carga 04"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Cliente A", "Cliente B"])

    def test_carretas_disponiveis_vem_da_base_liberada(self):
        self._criar_liberacao()

        response = self.client.get(
            reverse("expedicao:carretas"),
            {
                "data_carga": "2026-04-27",
                "carga": "Carga 04",
                "cliente": "Cliente A",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "Recurso": "034550VM",
                    "Qtde": 2.0,
                    "PED_NUMEROSERIE": "SERIE-01",
                    "cor": "vermelho",
                },
                {
                    "Recurso": "034550VM",
                    "Qtde": 1.0,
                    "PED_NUMEROSERIE": "SERIE-02",
                    "cor": "vermelho",
                },
            ],
        )

    def test_criar_caixa_usa_nome_cliente_no_carregamento(self):
        self._criar_liberacao()

        with patch(
            "apontamento_exped.views._criar_pendencias_para_carretas_carga",
            return_value={"pendencias_criadas": 0, "carretas_sem_componentes": []},
        ):
            response = self.client.post(
                reverse("expedicao:criar_caixa"),
                data={
                    "data_carga": "2026-04-27",
                    "carga_nome": "Carga 04",
                    "cliente_codigo": "Cliente A",
                    "observacoes": "",
                    "itens": [
                        {
                            "codigo_peca": "034550VM",
                            "quantidade": 2,
                            "cor": "vermelho",
                        }
                    ],
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["cliente"], "Cliente A")
