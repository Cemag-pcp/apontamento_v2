from unittest.mock import patch

import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localtime
from django.utils import timezone

from cargas.models import (
    CargaLiberada,
    CargaLiberadaAlteracao,
    CargaLiberadaItem,
    CargaLiberadaVersao,
    LinkAcompanhamento,
)
from cargas.services import (
    liberar_cargas_periodo,
    listar_cargas_liberadas_para_planejamento,
    listar_cargas_liberadas_periodo,
)
from cargas.utils import gerar_sequenciamento
from core.models import Ordem, Profile
from apontamento_exped.models import Carga as CargaExpedicao


class CargasLiberacaoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pcp_teste", password="123456")
        Profile.objects.create(user=self.user, tipo_acesso="pcp")
        self.client.login(username="pcp_teste", password="123456")

    @staticmethod
    def _date(value):
        from datetime import date

        return date.fromisoformat(value)

    def _payload_base(self):
        return {
            "cargas": [
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "CBH6-2E",
                    "quantidade": 1,
                    "carga": "Carga 04",
                    "cliente": "CLI001",
                    "presente_no_carreta": "✅",
                },
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "CBHM5000",
                    "quantidade": 2,
                    "carga": "Carga 04",
                    "cliente": "CLI001",
                    "presente_no_carreta": "❌",
                },
                {
                    "data_carga": "2026-04-28",
                    "codigo_recurso": "CBHM6000",
                    "quantidade": 3,
                    "carga": "Carga 01",
                    "cliente": "CLI002",
                    "presente_no_carreta": "✅",
                },
            ],
            "celulas": [],
        }

    @patch("cargas.services.consultar_carretas_detalhado")
    def test_primeira_liberacao_cria_modelos_e_log_inicial(self, consultar_mock):
        consultar_mock.return_value = self._payload_base()

        resultado = liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        self.assertEqual(resultado["total_cargas_liberadas"], 2)
        self.assertEqual(CargaLiberada.objects.count(), 2)
        self.assertEqual(CargaLiberadaVersao.objects.count(), 2)
        self.assertEqual(CargaLiberadaItem.objects.count(), 3)
        self.assertEqual(
            CargaLiberadaItem.objects.get(codigo_recurso="CBH6-2E").cliente,
            "CLI001",
        )
        self.assertEqual(
            CargaLiberadaItem.objects.get(codigo_recurso="CBH6-2E").cliente_codigo,
            "CLI001",
        )
        self.assertEqual(
            CargaLiberadaItem.objects.get(codigo_recurso="CBH6-2E").presente_no_carreta,
            "✅",
        )
        self.assertEqual(
            CargaLiberadaAlteracao.objects.filter(tipo_alteracao="liberacao_inicial").count(),
            2,
        )

    @patch("cargas.services.consultar_carretas_detalhado")
    def test_reliberacao_cria_nova_versao_com_mesmo_uuid(self, consultar_mock):
        consultar_mock.return_value = self._payload_base()
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        carga = CargaLiberada.objects.get(carga_nome="Carga 04", data_carga="2026-04-27")
        uuid_inicial = carga.carga_uuid

        consultar_mock.return_value = self._payload_base()
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        carga.refresh_from_db()
        self.assertEqual(carga.carga_uuid, uuid_inicial)
        self.assertEqual(carga.versoes.count(), 2)
        self.assertEqual(carga.versoes.order_by("-versao").first().versao, 2)

    @patch("cargas.services.consultar_carretas_detalhado")
    def test_diff_gera_logs_de_adicao_remocao_e_alteracao(self, consultar_mock):
        consultar_mock.return_value = {
            "cargas": [
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "A",
                    "quantidade": 1,
                    "carga": "Carga 04",
                    "presente_no_carreta": "✅",
                },
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "B",
                    "quantidade": 2,
                    "carga": "Carga 04",
                    "presente_no_carreta": "✅",
                },
            ],
            "celulas": [],
        }
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-27"),
        )

        consultar_mock.return_value = {
            "cargas": [
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "A",
                    "quantidade": 5,
                    "carga": "Carga 04",
                    "presente_no_carreta": "✅",
                },
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "C",
                    "quantidade": 9,
                    "carga": "Carga 04",
                    "presente_no_carreta": "❌",
                },
            ],
            "celulas": [],
        }
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-27"),
        )

        carga = CargaLiberada.objects.get(carga_nome="Carga 04")
        tipos = list(
            carga.alteracoes.exclude(tipo_alteracao="liberacao_inicial")
            .order_by("tipo_alteracao")
            .values_list("tipo_alteracao", flat=True)
        )
        self.assertEqual(
            tipos,
            ["item_adicionado", "item_removido", "quantidade_alterada"],
        )

    def test_api_rejeita_datas_invalidas(self):
        response = self.client.post(
            reverse("cargas:liberar_cargas"),
            data='{"data_inicio":"2026-04-28","data_fim":"2026-04-27"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("menor ou igual", response.json()["error"])

    @patch("cargas.views.liberar_cargas_periodo")
    def test_api_liberacao_grava_usuario_e_retorna_resumo(self, liberar_mock):
        liberar_mock.return_value = {
            "total_cargas_liberadas": 1,
            "total_versoes_criadas": 1,
            "cargas": [
                {
                    "carga_uuid": "123",
                    "data_carga": "2026-04-27",
                    "carga": "Carga 04",
                    "versao": 1,
                }
            ],
        }

        response = self.client.post(
            reverse("cargas:liberar_cargas"),
            data='{"data_inicio":"2026-04-27","data_fim":"2026-04-27"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["total_cargas_liberadas"], 1)
        kwargs = liberar_mock.call_args.kwargs
        self.assertEqual(kwargs["usuario"], self.user)

    def test_tela_liberacao_renderiza(self):
        response = self.client.get(reverse("cargas:liberacao"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Liberar carga")
        self.assertContains(response, 'data-interactive="false"', html=False)
        self.assertContains(response, '/cargas/api/andamento-liberacoes/', html=False)

    def test_api_andamento_liberacoes_retorna_cargas_do_periodo(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
            data_sugerida_planejamento=self._date("2026-04-29"),
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )

        response = self.client.get(
            reverse("cargas:andamento_liberacoes"),
            {"start": "2026-04-01", "end": "2026-05-01"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["title"], "Carga 04 v2")
        self.assertEqual(payload[0]["extendedProps"]["versao"], 2)
        self.assertEqual(payload[0]["extendedProps"]["data_carga"], "27/04/2026")
        self.assertEqual(payload[0]["extendedProps"]["data_sugerida_planejamento"], "29/04/2026")
        self.assertEqual(
            payload[0]["extendedProps"]["liberado_em"],
            localtime(versao.liberado_em).strftime("%d/%m/%Y %H:%M"),
        )

    def test_api_detalhes_liberacao_retorna_itens_ultima_versao(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
            data_sugerida_planejamento=self._date("2026-04-29"),
        )
        versao_1 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao_1,
            codigo_recurso="ITEM-OLD",
            quantidade=1,
        )
        versao_2 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao_2,
            codigo_recurso="ITEM-NEW",
            quantidade=3,
            cliente="Cliente A",
        )

        response = self.client.get(
            reverse("cargas:detalhes_liberacao", kwargs={"carga_uuid": carga.carga_uuid})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["versao"], 2)
        self.assertEqual(payload["carga"], "Carga 04")
        self.assertEqual(payload["liberado_por"], self.user.username)
        self.assertEqual(payload["data_sugerida_planejamento"], "2026-04-29")
        self.assertTrue(payload["tem_data_sugerida"])
        self.assertEqual(
            payload["liberado_em"],
            localtime(versao_2.liberado_em).strftime("%d/%m/%Y %H:%M"),
        )
        self.assertEqual(
            payload["itens"],
            [{"cliente": "Cliente A", "codigo_recurso": "ITEM-NEW", "quantidade": 3.0, "presente_no_carreta": ""}],
        )

    def test_listar_cargas_liberadas_periodo_usa_ultima_versao(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
            data_sugerida_planejamento=self._date("2026-04-29"),
        )
        versao_1 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao_1,
            codigo_recurso="ITEM-OLD",
            quantidade=1,
        )
        versao_2 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao_2,
            codigo_recurso="ITEM-NEW",
            quantidade=5,
        )

        payload = listar_cargas_liberadas_periodo(
            self._date("2026-04-27"),
            self._date("2026-04-27"),
        )

        self.assertEqual(
            payload["cargas"],
            [
                {
                    "data_carga": "2026-04-27",
                    "data_sugerida_planejamento": "2026-04-29",
                    "codigo_recurso": "ITEM-NEW",
                    "quantidade": 5.0,
                    "presente_no_carreta": "",
                    "carga": "Carga 04",
                    "versao": 2,
                }
            ],
        )

    def test_api_cargas_liberadas_retorna_base_do_sequenciamento(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=3,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="ITEM-SEQ",
            quantidade=2,
        )

        response = self.client.get(
            reverse("cargas:buscar_cargas_liberadas"),
            {"data_inicio": "2026-04-27", "data_fim": "2026-04-27"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["cargas"]["cargas"][0]["codigo_recurso"], "ITEM-SEQ")
        self.assertEqual(payload["cargas"]["cargas"][0]["versao"], 3)
        self.assertEqual(payload["cargas"]["cargas"][0]["presente_no_carreta"], "")
        self.assertEqual(payload["cargas"]["cargas"][0]["data_sugerida_planejamento"], "")

    def test_listar_cargas_liberadas_para_planejamento_retorna_ultima_versao(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        versao_2 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )

        payload = listar_cargas_liberadas_para_planejamento(
            self._date("2026-04-27"),
            self._date("2026-04-27"),
        )

        self.assertEqual(
            payload,
            [
                {
                    "carga_liberada_id": carga.id,
                    "carga_liberada_versao_id": versao_2.id,
                    "carga_uuid": str(carga.carga_uuid),
                    "versao_uuid": str(versao_2.versao_uuid),
                    "data_carga": self._date("2026-04-27"),
                    "data_sugerida_planejamento": None,
                    "carga": "Carga 04",
                    "versao": 2,
                }
            ],
        )

    @patch("cargas.views.processar_ordens_montagem")
    @patch("cargas.views.gerar_sequenciamento")
    def test_gerar_planejamento_vincula_ordem_a_carga_liberada(self, gerar_mock, processar_mock):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=3,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        gerar_mock.return_value = pd.DataFrame(
            [
                {
                    "Código": "ITEM-SEQ",
                    "Peca": "Peça teste",
                    "Célula": "CEL-01",
                    "Datas": pd.Timestamp("2026-04-27"),
                    "Qtde_total": 2,
                    "Carga": "Carga 04",
                }
            ]
        )
        processar_mock.return_value = {"message": "ok", "ordens": []}

        response = self.client.get(
            reverse("cargas:gerar_dados_sequenciamento"),
            {
                "data_inicio": "2026-04-27",
                "data_fim": "2026-04-27",
                "setor": "montagem",
            },
        )

        self.assertEqual(response.status_code, 200)
        processar_mock.assert_called_once()
        ordens = processar_mock.call_args.args[1]
        self.assertEqual(len(ordens), 1)
        self.assertEqual(ordens[0]["carga_liberada_id"], carga.id)
        self.assertEqual(ordens[0]["carga_liberada_versao_id"], versao.id)

    @patch("cargas.views.processar_ordens_montagem")
    @patch("cargas.views.gerar_sequenciamento")
    def test_gerar_planejamento_aplica_data_sugerida_e_persiste_na_liberacao(self, gerar_mock, processar_mock):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        gerar_mock.return_value = pd.DataFrame(
            [
                {
                    "Código": "ITEM-SEQ",
                    "Peca": "Peça teste",
                    "Célula": "CEL-01",
                    "Datas": pd.Timestamp("2026-04-27"),
                    "Qtde_total": 2,
                    "Carga": "Carga 04",
                }
            ]
        )
        processar_mock.return_value = {"message": "ok", "ordens": []}

        response = self.client.get(
            reverse("cargas:gerar_dados_sequenciamento"),
            {
                "data_inicio": "2026-04-27",
                "data_fim": "2026-04-27",
                "setor": "montagem",
                "sugestoes_datas": '{"2026-04-27":"2026-04-29"}',
            },
        )

        self.assertEqual(response.status_code, 200)
        ordens = processar_mock.call_args.args[1]
        self.assertEqual(ordens[0]["data_carga"], "2026-04-29")
        carga.refresh_from_db()
        self.assertEqual(carga.data_sugerida_planejamento, self._date("2026-04-29"))
        self.assertEqual(ordens[0]["carga_liberada_id"], carga.id)
        self.assertEqual(ordens[0]["carga_liberada_versao_id"], versao.id)

    def test_gerar_planejamento_rejeita_conflito_de_datas_sugeridas(self):
        for data_carga, carga_nome in [
            ("2026-04-27", "Carga 04"),
            ("2026-04-28", "Carga 05"),
        ]:
            carga = CargaLiberada.objects.create(
                data_carga=self._date(data_carga),
                carga_nome=carga_nome,
            )
            CargaLiberadaVersao.objects.create(
                carga_liberada=carga,
                versao=1,
                data_inicio_pesquisa=self._date(data_carga),
                data_fim_pesquisa=self._date(data_carga),
                liberado_por=self.user,
                payload_snapshot={},
            )

        response = self.client.get(
            reverse("cargas:gerar_dados_sequenciamento"),
            {
                "data_inicio": "2026-04-27",
                "data_fim": "2026-04-28",
                "setor": "montagem",
                "sugestoes_datas": '{"2026-04-27":"2026-04-29","2026-04-28":"2026-04-29"}',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Conflito de sugestão de datas", response.json()["error"])

    def test_aplicar_data_sugerida_liberacao_atualiza_carga_e_links(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
            data_sugerida_planejamento=self._date("2026-04-29"),
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="ITEM-NEW",
            quantidade=3,
            cliente="Cliente A",
            cliente_codigo="CLI001",
        )
        LinkAcompanhamento.objects.create(
            data_carga=self._date("2026-04-27"),
            cliente="Cliente A",
        )
        ordem = Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-04-27"),
            carga_liberada=carga,
            carga_liberada_versao=versao,
        )

        response = self.client.post(
            reverse("cargas:aplicar_data_sugerida_liberacao", kwargs={"carga_uuid": carga.carga_uuid}),
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        carga.refresh_from_db()
        ordem.refresh_from_db()
        self.assertEqual(carga.data_carga, self._date("2026-04-29"))
        self.assertIsNone(carga.data_sugerida_planejamento)
        self.assertEqual(ordem.data_carga, self._date("2026-04-29"))
        self.assertEqual(LinkAcompanhamento.objects.filter(data_carga=self._date("2026-04-29"), cliente="Cliente A").count(), 1)
        self.assertFalse(LinkAcompanhamento.objects.filter(data_carga=self._date("2026-04-27"), cliente="Cliente A").exists())

    def test_aplicar_data_sugerida_liberacao_rejeita_conflito_mesma_data_nome(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
            data_sugerida_planejamento=self._date("2026-04-29"),
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberada.objects.create(
            data_carga=self._date("2026-04-29"),
            carga_nome="Carga 04",
        )

        response = self.client.post(
            reverse("cargas:aplicar_data_sugerida_liberacao", kwargs={"carga_uuid": carga.carga_uuid}),
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Já existe uma carga com esse nome na data sugerida", response.json()["error"])

    def test_processar_ordem_montagem_grava_relacao_com_carga_liberada(self):
        from cadastro.models import Maquina, Setor
        from cargas.utils import processar_ordens_montagem

        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        setor = Setor.objects.create(nome="montagem")
        Maquina.objects.create(nome="CEL-01", setor=setor)

        with patch("cargas.utils.gerar_e_salvar_qrcode", return_value=None):
            resultado = processar_ordens_montagem(
                request=None,
                ordens_data=[
                    {
                        "obs": "Ordem gerada automaticamente",
                        "peca_nome": "ITEM-SEQ - Peça teste",
                        "qtd_planejada": 2,
                        "data_carga": "2026-04-27",
                        "setor_conjunto": "CEL-01",
                        "carga_liberada_id": carga.id,
                        "carga_liberada_versao_id": versao.id,
                    }
                ],
                grupo_maquina="montagem",
            )

        self.assertNotIn("error", resultado)
        ordem = Ordem.objects.get(grupo_maquina="montagem", data_carga="2026-04-27")
        self.assertEqual(ordem.carga_liberada_id, carga.id)
        self.assertEqual(ordem.carga_liberada_versao_id, versao.id)

    def test_api_status_carga_retorna_aguardando_liberacao(self):
        response = self.client.get(
            reverse("cargas:status_carga_por_data"),
            {"data_carga": "2026-04-27", "cliente": "Cliente A"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "aguardando_liberacao")
        self.assertEqual(response.json()["descricao"], "Aguardando liberação")

    def test_api_status_carga_retorna_liberado(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="ITEM-NEW",
            quantidade=3,
            cliente="Cliente A",
            cliente_codigo="CLI001",
        )

        response = self.client.get(
            reverse("cargas:status_carga_por_data"),
            {"data_carga": "2026-04-27", "cliente": "Cliente A"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "liberado")
        self.assertEqual(response.json()["descricao"], "Liberado")
        self.assertEqual(
            response.json()["historico"],
            [
                {
                    "status": "liberado",
                    "descricao": "Liberado",
                    "data": localtime(versao.liberado_em).strftime("%d/%m/%Y"),
                }
            ],
        )

    def test_api_status_carga_retorna_em_fabricacao_quando_ha_montagem(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="ITEM-NEW",
            quantidade=3,
            cliente="Cliente A",
            cliente_codigo="CLI001",
        )
        ordem = Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-04-27"),
            carga_liberada=carga,
            carga_liberada_versao=versao,
        )

        response = self.client.get(
            reverse("cargas:status_carga_por_data"),
            {"data_carga": "2026-04-27", "cliente": "Cliente A"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "em_fabricacao")
        self.assertEqual(response.json()["descricao"], "Em fabricação")
        self.assertEqual(
            response.json()["historico"],
            [
                {
                    "status": "liberado",
                    "descricao": "Liberado",
                    "data": localtime(versao.liberado_em).strftime("%d/%m/%Y"),
                },
                {
                    "status": "em_fabricacao",
                    "descricao": "Em fabricação",
                    "data": localtime(ordem.data_criacao).strftime("%d/%m/%Y"),
                },
            ],
        )


class SequenciamentoMontagemTests(TestCase):
    @patch("cargas.utils.get_data_from_sheets")
    def test_gerar_sequenciamento_montagem_filtra_por_carga_e_nao_duplica_base(self, get_data_mock):
        base_carretas = pd.DataFrame(
            [
                {
                    "Recurso": "12345",
                    "Código": "54321",
                    "Peca": "Conjunto Teste",
                    "Qtde": 2,
                    "Célula": "CEL-01",
                    "Etapa": "Montagem",
                    "Etapa2": "",
                    "Etapa3": "",
                    "Etapa4": "",
                    "Etapa5": "",
                },
                {
                    "Recurso": "12345",
                    "Código": "54321",
                    "Peca": "Conjunto Teste",
                    "Qtde": 2,
                    "Célula": "CEL-01",
                    "Etapa": "Montagem",
                    "Etapa2": "",
                    "Etapa3": "",
                    "Etapa4": "",
                    "Etapa5": "",
                },
            ]
        )
        base_carga = pd.DataFrame(
            [
                {
                    "PED_PREVISAOEMISSAODOC": "05/05/2026",
                    "PED_RECURSO.CODIGO": "12345",
                    "PED_QUANTIDADE": 3,
                    "Carga": "Carga A",
                },
                {
                    "PED_PREVISAOEMISSAODOC": "05/05/2026",
                    "PED_RECURSO.CODIGO": "12345",
                    "PED_QUANTIDADE": 4,
                    "Carga": "Carga B",
                },
            ]
        )
        get_data_mock.return_value = (base_carretas, base_carga)

        resultado = gerar_sequenciamento(
            "2026-05-05",
            "2026-05-05",
            "montagem",
            carga="Carga A",
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]["Carga"], "Carga A")
        self.assertEqual(int(resultado.iloc[0]["Qtde_total"]), 6)

    @patch("cargas.utils.get_data_from_sheets")
    def test_gerar_sequenciamento_solda_filtra_por_carga_e_nao_duplica_base(self, get_data_mock):
        base_carretas = pd.DataFrame(
            [
                {
                    "Recurso": "12345",
                    "Código": "54321",
                    "Peca": "Conjunto Solda",
                    "Qtde": 2,
                    "Célula": "CEL-S1",
                    "Etapa": "",
                    "Etapa2": "",
                    "Etapa3": "Solda",
                    "Etapa4": "",
                    "Etapa5": "",
                },
                {
                    "Recurso": "12345",
                    "Código": "54321",
                    "Peca": "Conjunto Solda",
                    "Qtde": 2,
                    "Célula": "CEL-S1",
                    "Etapa": "",
                    "Etapa2": "",
                    "Etapa3": "Solda",
                    "Etapa4": "",
                    "Etapa5": "",
                },
            ]
        )
        base_carga = pd.DataFrame(
            [
                {
                    "PED_PREVISAOEMISSAODOC": "05/05/2026",
                    "PED_RECURSO.CODIGO": "12345",
                    "PED_QUANTIDADE": 3,
                    "Carga": "Carga A",
                },
                {
                    "PED_PREVISAOEMISSAODOC": "05/05/2026",
                    "PED_RECURSO.CODIGO": "12345",
                    "PED_QUANTIDADE": 4,
                    "Carga": "Carga B",
                },
            ]
        )
        get_data_mock.return_value = (base_carretas, base_carga)

        resultado = gerar_sequenciamento(
            "2026-05-05",
            "2026-05-05",
            "solda",
            carga="Carga A",
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]["Carga"], "Carga A")
        self.assertEqual(int(resultado.iloc[0]["Qtde_total"]), 6)

    def test_api_status_carga_retorna_expedida(self):
        carga_liberada = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga_liberada,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="ITEM-NEW",
            quantidade=3,
            cliente="Cliente A",
            cliente_codigo="CLI001",
        )
        ordem = Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-04-27"),
            carga_liberada=carga_liberada,
            carga_liberada_versao=versao,
        )
        carga_expedicao = CargaExpedicao.objects.create(
            nome="Carga 04_Cliente A_20260427_101010",
            carga="Carga 04",
            data_carga=self._date("2026-04-27"),
            cliente="Cliente A",
            obs_pacote="",
            stage="despachado",
        )
        data_criacao = timezone.now()
        data_despachado = timezone.now()
        CargaExpedicao.objects.filter(pk=carga_expedicao.pk).update(
            data_criacao=data_criacao,
            data_despachado=data_despachado,
        )
        carga_expedicao.refresh_from_db()

        response = self.client.get(
            reverse("cargas:status_carga_por_data"),
            {"data_carga": "2026-04-27", "cliente": "Cliente A"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "expedida")
        self.assertEqual(response.json()["descricao"], "Expedida")
        self.assertEqual(
            response.json()["historico"],
            [
                {
                    "status": "liberado",
                    "descricao": "Liberado",
                    "data": localtime(versao.liberado_em).strftime("%d/%m/%Y"),
                },
                {
                    "status": "em_fabricacao",
                    "descricao": "Em fabricação",
                    "data": localtime(ordem.data_criacao).strftime("%d/%m/%Y"),
                },
                {
                    "status": "liberado_expedicao",
                    "descricao": "Liberado para expedição",
                    "data": localtime(carga_expedicao.data_criacao).strftime("%d/%m/%Y"),
                },
                {
                    "status": "expedida",
                    "descricao": "Expedida",
                    "data": localtime(carga_expedicao.data_despachado).strftime("%d/%m/%Y"),
                },
            ],
        )
