from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cadastro.models import CarretasExplodidas
from cargas.models import CargaLiberada, CargaLiberadaItem, CargaLiberadaVersao
from apontamento_exped.models import Carga, CarretaCarga, PendenciasPacote
from apontamento_exped.views import _buscar_componentes_por_carreta, normalize_carreta_text


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


class ExpedicaoCarretaNormalizationTests(TestCase):
    def test_busca_componentes_ignora_espacos_duplicados_no_nome_da_carreta(self):
        CarretasExplodidas.objects.create(
            carreta="CBHM4500 SS RD MM M17 [EIXO 5000]",
            codigo_peca="PEC001",
            descricao_peca="PEC001 - Componente teste",
            total_peca="2",
            primeiro_processo="PINTAR",
        )

        grupos = _buscar_componentes_por_carreta(
            ["CBHM4500 SS RD MM M17  [EIXO 5000]"]
        )

        chave = normalize_carreta_text("CBHM4500 SS RD MM M17  [EIXO 5000]")
        self.assertEqual(list(grupos.keys()), [chave])
        self.assertEqual(grupos[chave][0]["codigo_base"], "PEC001")
        self.assertEqual(grupos[chave][0]["total_por_carreta"], 2)

    def test_reprocessar_carreta_gera_pendencias_mesmo_com_espacos_duplicados(self):
        carga = Carga.objects.create(
            nome="Carga teste",
            carga="Carga 01",
            data_carga="2026-05-15",
            cliente="Cliente X",
            obs_pacote="",
            stage="verificacao",
        )
        CarretaCarga.objects.create(
            carga=carga,
            carreta="CBHM4500 SS RD MM M17  [EIXO 5000]",
            quantidade=3,
            cor="sem-cor",
        )
        CarretasExplodidas.objects.create(
            carreta="CBHM4500 SS RD MM M17 [EIXO 5000]",
            codigo_peca="PEC001",
            descricao_peca="PEC001 - Componente teste",
            total_peca="2",
            primeiro_processo="PINTAR",
        )

        response = self.client.post(
            reverse("expedicao:reatualizar_carretas_faltantes", args=[carga.id]),
            data={"carreta": "CBHM4500 SS RD MM M17  [EIXO 5000]"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PendenciasPacote.objects.count(), 1)
        pendencia = PendenciasPacote.objects.get()
        self.assertEqual(pendencia.codigo, "PEC001")
        self.assertEqual(pendencia.qt_necessaria, 6)
