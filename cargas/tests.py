import json
from unittest.mock import patch

import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localtime
from django.utils import timezone

from cadastro.models import Maquina, Setor
from apontamento_montagem.models import PecasOrdem as PecasOrdemMontagem
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
from cargas.utils import buscar_celulas, gerar_sequenciamento
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
    def test_reliberacao_exclui_carga_que_sumiu_da_consulta(self, consultar_mock):
        consultar_mock.return_value = self._payload_base()
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        consultar_mock.return_value = {
            "cargas": [
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "CBH6-2E",
                    "quantidade": 1,
                    "carga": "Carga 04",
                    "cliente": "CLI001",
                    "presente_no_carreta": "âœ…",
                }
            ],
            "celulas": [],
        }

        resultado = liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        carga_inativada = CargaLiberada.objects.get(
            data_carga=self._date("2026-04-28"),
            carga_nome="Carga 01",
        )
        self.assertFalse(carga_inativada.ativo)
        self.assertIsNotNone(carga_inativada.inativada_em)
        self.assertEqual(resultado["total_cargas_inativadas_automaticamente"], 1)
        self.assertEqual(
            resultado["cargas_inativadas_automaticamente"][0]["carga"],
            "Carga 01",
        )
        self.assertTrue(
            CargaLiberadaAlteracao.objects.filter(
                carga_liberada=carga_inativada,
                tipo_alteracao="carga_inativada",
            ).exists()
        )

    @patch("cargas.services.consultar_carretas_detalhado")
    def test_reliberacao_exclui_carga_sumida_mesmo_com_ordem_vinculada(self, consultar_mock):
        consultar_mock.return_value = self._payload_base()
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        carga_sumida = CargaLiberada.objects.get(
            data_carga=self._date("2026-04-28"),
            carga_nome="Carga 01",
        )
        versao = carga_sumida.versoes.order_by("-versao").first()
        ordem = Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-04-28"),
            carga_liberada=carga_sumida,
            carga_liberada_versao=versao,
        )

        consultar_mock.return_value = {
            "cargas": [
                {
                    "data_carga": "2026-04-27",
                    "codigo_recurso": "CBH6-2E",
                    "quantidade": 1,
                    "carga": "Carga 04",
                    "cliente": "CLI001",
                    "presente_no_carreta": "âœ…",
                }
            ],
            "celulas": [],
        }

        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        ordem.refresh_from_db()
        carga_sumida.refresh_from_db()
        self.assertFalse(carga_sumida.ativo)
        self.assertEqual(ordem.carga_liberada_id, carga_sumida.id)
        self.assertEqual(ordem.carga_liberada_versao_id, versao.id)

    @patch("cargas.services.consultar_carretas_detalhado")
    def test_reliberacao_reativa_carga_quando_volta_para_consulta(self, consultar_mock):
        consultar_mock.return_value = self._payload_base()
        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-27"),
            data_fim=self._date("2026-04-28"),
        )

        carga = CargaLiberada.objects.get(
            data_carga=self._date("2026-04-28"),
            carga_nome="Carga 01",
        )
        carga.ativo = False
        carga.inativada_em = timezone.now()
        carga.save(update_fields=["ativo", "inativada_em", "atualizado_em"])

        consultar_mock.return_value = {
            "cargas": [
                {
                    "data_carga": "2026-04-28",
                    "codigo_recurso": "CBHM6000",
                    "quantidade": 4,
                    "carga": "Carga 01",
                    "cliente": "CLI002",
                    "presente_no_carreta": "âœ…",
                },
            ],
            "celulas": [],
        }

        liberar_cargas_periodo(
            usuario=self.user,
            data_inicio=self._date("2026-04-28"),
            data_fim=self._date("2026-04-28"),
        )

        carga.refresh_from_db()
        self.assertTrue(carga.ativo)
        self.assertIsNone(carga.inativada_em)
        self.assertTrue(
            CargaLiberadaAlteracao.objects.filter(
                carga_liberada=carga,
                tipo_alteracao="carga_reativada",
            ).exists()
        )

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
        self.assertEqual(kwargs["incluir_sheet_rows_sem_numero_serie"], [])

    @patch("cargas.views.liberar_cargas_periodo")
    def test_api_liberacao_envia_itens_sem_numero_serie_selecionados(self, liberar_mock):
        liberar_mock.return_value = {
            "total_cargas_liberadas": 1,
            "total_versoes_criadas": 1,
            "cargas": [],
        }

        response = self.client.post(
            reverse("cargas:liberar_cargas"),
            data='{"data_inicio":"2026-04-27","data_fim":"2026-04-27","itens_sem_numero_serie_selecionados":[12,18]}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        kwargs = liberar_mock.call_args.kwargs
        self.assertEqual(kwargs["incluir_sheet_rows_sem_numero_serie"], [12, 18])

    def test_tela_liberacao_renderiza(self):
        response = self.client.get(reverse("cargas:liberacao"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Liberar carga")
        self.assertContains(response, 'id="modalExcluirLiberacao"', html=False)
        self.assertContains(response, 'id="modalHistoricoLiberacoes"', html=False)
        self.assertContains(response, 'id="confirmarExcluirLiberacao"', html=False)
        self.assertContains(response, 'data-interactive="false"', html=False)
        self.assertContains(response, '/cargas/api/andamento-liberacoes/', html=False)
        self.assertContains(response, 'data-history-dates-url="/cargas/api/liberacoes/historico-datas/"', html=False)
        self.assertContains(response, 'data-history-url="/cargas/api/liberacoes/historico/"', html=False)

    def test_api_datas_historico_inclui_cargas_ativas_e_inativas(self):
        CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga ativa",
        )
        CargaLiberada.objects.create(
            data_carga=self._date("2026-04-28"),
            carga_nome="Carga inativa",
            ativo=False,
            inativada_em=timezone.now(),
        )

        response = self.client.get(
            reverse("cargas:datas_historico_liberacoes"),
            {"start": "2026-04-01", "end": "2026-05-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["datas"],
            ["2026-04-27", "2026-04-28"],
        )

    def test_api_datas_historico_rejeita_intervalo_invalido(self):
        sem_datas = self.client.get(reverse("cargas:datas_historico_liberacoes"))
        invertido = self.client.get(
            reverse("cargas:datas_historico_liberacoes"),
            {"start": "2026-05-01", "end": "2026-04-01"},
        )

        self.assertEqual(sem_datas.status_code, 400)
        self.assertEqual(invertido.status_code, 400)

    def test_api_historico_diario_retorna_cargas_versoes_e_alteracoes(self):
        data_carga = self._date("2026-04-27")
        carga_ativa = CargaLiberada.objects.create(
            data_carga=data_carga,
            carga_nome="Carga 01",
        )
        versao_1 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga_ativa,
            versao=1,
            data_inicio_pesquisa=data_carga,
            data_fim_pesquisa=data_carga,
            liberado_por=self.user,
            payload_snapshot={},
        )
        versao_2 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga_ativa,
            versao=2,
            data_inicio_pesquisa=data_carga,
            data_fim_pesquisa=data_carga,
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaAlteracao.objects.create(
            carga_liberada=carga_ativa,
            versao_origem=None,
            versao_destino=versao_1,
            tipo_alteracao="liberacao_inicial",
            detalhes={"mensagem": "Primeira liberação da carga."},
        )
        CargaLiberadaAlteracao.objects.create(
            carga_liberada=carga_ativa,
            versao_origem=versao_1,
            versao_destino=versao_2,
            tipo_alteracao="item_adicionado",
            codigo_recurso="ITEM-A",
            quantidade_nova=3,
            detalhes={"cliente_codigo": "CLI-1", "numero_serie": "SERIE-1"},
        )
        CargaLiberadaAlteracao.objects.create(
            carga_liberada=carga_ativa,
            versao_origem=versao_1,
            versao_destino=versao_2,
            tipo_alteracao="item_removido",
            codigo_recurso="ITEM-B",
            quantidade_anterior=2,
        )
        CargaLiberadaAlteracao.objects.create(
            carga_liberada=carga_ativa,
            versao_origem=versao_1,
            versao_destino=versao_2,
            tipo_alteracao="quantidade_alterada",
            codigo_recurso="ITEM-C",
            quantidade_anterior=1,
            quantidade_nova=5,
        )

        carga_inativa = CargaLiberada.objects.create(
            data_carga=data_carga,
            carga_nome="Carga 02",
            ativo=False,
            inativada_em=timezone.now(),
        )
        versao_inativa = CargaLiberadaVersao.objects.create(
            carga_liberada=carga_inativa,
            versao=1,
            data_inicio_pesquisa=data_carga,
            data_fim_pesquisa=data_carga,
            liberado_por=self.user,
            payload_snapshot={},
        )
        for tipo in ("carga_inativada", "carga_reativada"):
            CargaLiberadaAlteracao.objects.create(
                carga_liberada=carga_inativa,
                versao_origem=versao_inativa,
                versao_destino=versao_inativa,
                tipo_alteracao=tipo,
                detalhes={"motivo": f"Motivo {tipo}"},
            )

        response = self.client.get(
            reverse("cargas:historico_liberacoes_dia"),
            {"data": data_carga.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_formatada"], "27/04/2026")
        self.assertEqual([carga["carga"] for carga in payload["cargas"]], ["Carga 01", "Carga 02"])
        self.assertTrue(payload["cargas"][0]["ativo"])
        self.assertFalse(payload["cargas"][1]["ativo"])
        self.assertEqual(
            [versao["versao"] for versao in payload["cargas"][0]["versoes"]],
            [2, 1],
        )
        tipos_versao_2 = {
            alteracao["tipo"]
            for alteracao in payload["cargas"][0]["versoes"][0]["alteracoes"]
        }
        self.assertEqual(
            tipos_versao_2,
            {"item_adicionado", "item_removido", "quantidade_alterada"},
        )
        item_adicionado = next(
            alteracao
            for alteracao in payload["cargas"][0]["versoes"][0]["alteracoes"]
            if alteracao["tipo"] == "item_adicionado"
        )
        self.assertEqual(item_adicionado["cliente_codigo"], "CLI-1")
        self.assertEqual(item_adicionado["numero_serie"], "SERIE-1")
        self.assertEqual(
            {
                alteracao["tipo"]
                for alteracao in payload["cargas"][1]["versoes"][0]["alteracoes"]
            },
            {"carga_inativada", "carga_reativada"},
        )

    def test_api_historico_diario_inclui_versao_sem_alteracoes(self):
        data_carga = self._date("2026-04-27")
        carga = CargaLiberada.objects.create(
            data_carga=data_carga,
            carga_nome="Carga sem diferenças",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=data_carga,
            data_fim_pesquisa=data_carga,
            liberado_por=self.user,
            payload_snapshot={},
        )

        response = self.client.get(
            reverse("cargas:historico_liberacoes_dia"),
            {"data": data_carga.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["cargas"][0]["versoes"][0]["alteracoes"],
            [],
        )

    def test_api_historico_diario_rejeita_data_invalida(self):
        response = self.client.get(
            reverse("cargas:historico_liberacoes_dia"),
            {"data": "27-04-2026"},
        )

        self.assertEqual(response.status_code, 400)

    def test_apis_historico_exigem_autenticacao(self):
        self.client.logout()

        datas = self.client.get(
            reverse("cargas:datas_historico_liberacoes"),
            {"start": "2026-04-01", "end": "2026-05-01"},
        )
        historico = self.client.get(
            reverse("cargas:historico_liberacoes_dia"),
            {"data": "2026-04-27"},
        )

        self.assertEqual(datas.status_code, 302)
        self.assertEqual(historico.status_code, 302)

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

    def test_api_andamento_liberacoes_ignora_cargas_inativas(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
            ativo=False,
            inativada_em=timezone.now(),
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
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
        self.assertEqual(response.json(), [])

    def test_api_andamento_liberacoes_mantem_todas_as_cargas_do_dia(self):
        carga_v2 = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 01",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga_v2,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )

        carga_v1 = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga_v1,
            versao=1,
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
        self.assertEqual(len(payload), 2)
        self.assertEqual(
            {item["title"] for item in payload},
            {"Carga 01 v2", "Carga 04 v1"},
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
        self.assertTrue(payload["ativo"])
        self.assertEqual(payload["total_ordens_vinculadas"], 0)
        self.assertTrue(payload["pode_excluir"])
        self.assertEqual(
            payload["liberado_em"],
            localtime(versao_2.liberado_em).strftime("%d/%m/%Y %H:%M"),
        )
        self.assertEqual(
            payload["itens"],
            [{"cliente": "Cliente A", "codigo_recurso": "ITEM-NEW", "quantidade": 3.0, "presente_no_carreta": ""}],
        )

    def test_api_excluir_liberacao_remove_carga_sem_ordens_vinculadas(self):
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

        response = self.client.post(
            reverse("cargas:excluir_liberacao", kwargs={"carga_uuid": carga.carga_uuid}),
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        carga.refresh_from_db()
        self.assertFalse(carga.ativo)
        self.assertIsNotNone(carga.inativada_em)
        self.assertTrue(
            CargaLiberadaAlteracao.objects.filter(
                carga_liberada=carga,
                tipo_alteracao="carga_inativada",
            ).exists()
        )

    def test_api_excluir_liberacao_bloqueia_quando_ha_ordens_vinculadas(self):
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
        Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-04-27"),
            carga_liberada=carga,
            carga_liberada_versao=versao,
        )

        response = self.client.post(
            reverse("cargas:excluir_liberacao", kwargs={"carga_uuid": carga.carga_uuid}),
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(CargaLiberada.objects.filter(pk=carga.pk).exists())
        self.assertIn("ordem", response.json()["error"])

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

    def test_listar_cargas_liberadas_periodo_retorna_alerta_quando_ha_versoes_diferentes_no_mesmo_dia(self):
        carga_v2 = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 01",
        )
        versao_2 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga_v2,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao_2,
            codigo_recurso="ITEM-V2",
            quantidade=3,
        )

        carga_v1 = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao_1 = CargaLiberadaVersao.objects.create(
            carga_liberada=carga_v1,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao_1,
            codigo_recurso="ITEM-V1",
            quantidade=9,
        )

        payload = listar_cargas_liberadas_periodo(
            self._date("2026-04-27"),
            self._date("2026-04-27"),
        )

        self.assertEqual(len(payload["cargas"]), 2)
        self.assertEqual(
            payload["alertas_versao"],
            [
                {
                    "data_carga": "2026-04-27",
                    "maior_versao": 2,
                    "cargas_maior_versao": [
                        {
                            "carga": "Carga 01",
                            "versao": 2,
                            "carga_uuid": str(carga_v2.carga_uuid),
                        }
                    ],
                    "cargas_anteriores": [
                        {
                            "carga": "Carga 04",
                            "versao": 1,
                            "carga_uuid": str(carga_v1.carga_uuid),
                        }
                    ],
                }
            ],
        )

    @patch("cargas.services.buscar_celulas")
    def test_listar_cargas_liberadas_periodo_retorna_celulas_para_modal_montagem(self, buscar_celulas_mock):
        buscar_celulas_mock.return_value = ["CEL-01", "CEL-02"]

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
            codigo_recurso="012345",
            quantidade=2,
            presente_no_carreta="✅",
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="067890",
            quantidade=1,
            presente_no_carreta="✅",
        )

        payload = listar_cargas_liberadas_periodo(
            self._date("2026-04-27"),
            self._date("2026-04-27"),
        )

        buscar_celulas_mock.assert_called_once_with(["012345", "067890"])
        self.assertEqual(
            payload["celulas"],
            [{"celula": "CEL-01"}, {"celula": "CEL-02"}],
        )

    @patch("cargas.utils.get_base_carreta")
    def test_buscar_celulas_normaliza_recurso_com_sufixo_de_serie(self, get_base_carreta_mock):
        get_base_carreta_mock.return_value = pd.DataFrame(
            [
                {"Recurso": "034538", "Célula": "CHASSI"},
                {"Recurso": "067890", "Célula": "EIXO"},
            ]
        )

        celulas = list(buscar_celulas(["34538M21", "067890AN"]))

        self.assertEqual(celulas, ["CHASSI", "EIXO"])

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

    @patch("cargas.views.processar_ordens_montagem")
    @patch("cargas.views.gerar_sequenciamento")
    def test_gerar_planejamento_agrupar_mesmo_item_mesma_data(self, gerar_mock, processar_mock):
        carga_1 = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 01",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga_1,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        carga_2 = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 02",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga_2,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )

        gerar_mock.side_effect = [
            pd.DataFrame(
                [
                    {
                        "CÃ³digo": "1001",
                        "Peca": "LONGARINA",
                        "CÃ©lula": "CHASSI",
                        "Datas": pd.Timestamp("2026-04-27"),
                        "Qtde_total": 2,
                        "Carga": "Carga 01",
                    }
                ]
            ),
            pd.DataFrame(
                [
                    {
                        "CÃ³digo": "1001",
                        "Peca": "LONGARINA",
                        "CÃ©lula": "CHASSI",
                        "Datas": pd.Timestamp("2026-04-27"),
                        "Qtde_total": 3,
                        "Carga": "Carga 02",
                    }
                ]
            ),
        ]
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
        ordens = processar_mock.call_args.args[1]
        self.assertEqual(len(ordens), 1)
        self.assertEqual(ordens[0]["peca_nome"], "1001 - LONGARINA")
        self.assertEqual(ordens[0]["qtd_planejada"], 5)
        self.assertIsNone(ordens[0]["carga_liberada_id"])
        self.assertIsNone(ordens[0]["carga_liberada_versao_id"])

    @patch("cargas.views.processar_ordens_montagem")
    @patch("cargas.views.gerar_sequenciamento")
    def test_atualizar_planejamento_usa_fluxo_de_gerar_e_atualiza_quantidades(self, gerar_mock, processar_mock):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-04-27"),
            carga_nome="Carga 04",
        )
        versao_antiga = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        versao_atual = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-04-27"),
            data_fim_pesquisa=self._date("2026-04-27"),
            liberado_por=self.user,
            payload_snapshot={},
        )

        ordem = Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-04-27"),
            carga_liberada=carga,
            carga_liberada_versao=versao_antiga,
        )
        peca_ordem = PecasOrdemMontagem.objects.create(
            ordem=ordem,
            peca="1001 - LONGARINA",
            qtd_planejada=2,
        )

        gerar_mock.return_value = pd.DataFrame(
            [
                {
                    "Código": "1001",
                    "Peca": "LONGARINA",
                    "Célula": "CHASSI",
                    "Datas": pd.Timestamp("2026-04-27"),
                    "Qtde_total": 7,
                    "Carga": "Carga 04",
                }
            ]
        )
        processar_mock.return_value = {"message": "ok", "ordens": []}

        response = self.client.get(
            reverse("cargas:atualizar_ordem_existente"),
            {"data_inicio": "2026-04-27", "setor": "montagem"},
        )

        self.assertEqual(response.status_code, 200)
        ordem.refresh_from_db()
        peca_ordem.refresh_from_db()
        self.assertEqual(ordem.carga_liberada_versao_id, versao_atual.id)
        self.assertEqual(peca_ordem.qtd_planejada, 7)
        self.assertEqual(response.json()["novas_ordens_criadas"], 0)
        processar_mock.assert_called_once()
        self.assertEqual(processar_mock.call_args.args[1], [])

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


class VerificarPlanejamentoMontagemTests(TestCase):
    @staticmethod
    def _date(value):
        from datetime import date

        return date.fromisoformat(value)

    def setUp(self):
        self.user = User.objects.create_user(username="pcp_preview", password="123456")
        self.setor_montagem = Setor.objects.create(nome="montagem")
        self.maquina = Maquina.objects.create(
            nome="CHASSI",
            setor=self.setor_montagem,
            tipo="producao",
        )

    def _criar_carga_liberada_com_versoes(self):
        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-05-20"),
            carga_nome="Carga 01",
        )
        CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-05-20"),
            data_fim_pesquisa=self._date("2026-05-20"),
            liberado_por=self.user,
            payload_snapshot={"itens": [{"codigo_recurso": "OLD"}]},
        )
        versao_atual = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=2,
            data_inicio_pesquisa=self._date("2026-05-20"),
            data_fim_pesquisa=self._date("2026-05-20"),
            liberado_por=self.user,
            payload_snapshot={"itens": [{"codigo_recurso": "NEW"}]},
        )
        return carga, versao_atual

    @patch("cargas.services.gerar_sequenciamento")
    def test_verificacao_retorna_ordens_previstas_para_montagem(self, mock_gerar_sequenciamento):
        carga, versao_atual = self._criar_carga_liberada_com_versoes()
        mock_gerar_sequenciamento.return_value = pd.DataFrame(
            [
                {
                    "Código": "1001",
                    "Peca": "LONGARINA",
                    "Célula": "CHASSI",
                    "Datas": pd.Timestamp("2026-05-20"),
                    "Carga": "Carga 01",
                    "Qtde_total": 4,
                },
                {
                    "Código": "1002",
                    "Peca": "TRAVESSA",
                    "Célula": "CHASSI",
                    "Datas": pd.Timestamp("2026-05-20"),
                    "Carga": "Carga 01",
                    "Qtde_total": 2,
                },
            ]
        )

        response = self.client.get(
            reverse("cargas:verificar_planejamento_montagem"),
            {
                "data_inicio": "2026-05-20",
                "data_fim": "2026-05-20",
                "sugestoes_datas": "{}",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["setor"], "montagem")
        self.assertEqual(payload["total_cargas"], 1)
        self.assertEqual(payload["total_ordens"], 2)
        self.assertEqual(payload["datas_finais"], ["2026-05-20"])
        self.assertEqual(payload["maquinas_nao_cadastradas"], [])

        self.assertEqual(payload["cargas"][0]["carga"], carga.carga_nome)
        self.assertEqual(payload["cargas"][0]["versao"], 2)
        self.assertEqual(payload["cargas"][0]["carga_liberada_versao_id"], versao_atual.id)
        self.assertEqual(payload["ordens"][0]["carga_liberada_versao_id"], versao_atual.id)
        self.assertEqual(payload["ordens"][0]["setor_conjunto"], self.maquina.nome)
        self.assertEqual(payload["ordens"][0]["data_carga"], "2026-05-20")
        self.assertEqual(payload["resumo_por_carga_liberada"][str(carga.id)], 2)

    @patch("cargas.services.gerar_sequenciamento")
    def test_verificacao_ignora_ordens_existentes_por_ser_apenas_preview(self, mock_gerar_sequenciamento):
        self._criar_carga_liberada_com_versoes()
        Ordem.objects.create(
            grupo_maquina="montagem",
            data_carga=self._date("2026-05-20"),
            data_programacao=self._date("2026-05-17"),
            setor_conjunto=self.maquina.nome,
            obs="Ordem existente",
        )
        mock_gerar_sequenciamento.return_value = pd.DataFrame(
            [
                {
                    "Código": "1001",
                    "Peca": "LONGARINA",
                    "Célula": "CHASSI",
                    "Datas": pd.Timestamp("2026-05-20"),
                    "Carga": "Carga 01",
                    "Qtde_total": 4,
                }
            ]
        )

        response = self.client.get(
            reverse("cargas:preview_gerar_planejamento_montagem"),
            {
                "data_inicio": "2026-05-20",
                "data_fim": "2026-05-20",
                "sugestoes_datas": "{}",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_ordens"], 1)


class BuscarCarretasBaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pcp_busca_base", password="123456")
        Profile.objects.create(user=self.user, tipo_acesso="pcp")
        self.client.login(username="pcp_busca_base", password="123456")

    @patch("cargas.views.consultar_carretas_detalhado")
    def test_endpoint_retorna_detalhado_sem_agregar_linhas(self, consultar_detalhado_mock):
        consultar_detalhado_mock.return_value = {
            "cargas": [
                {
                    "data_carga": "2026-05-20",
                    "codigo_recurso": "FTC4300R CS RS/RS M24",
                    "quantidade": 1.0,
                    "presente_no_carreta": "✅",
                    "carga": "V ProdPrópria p Consumo",
                    "cliente": "SantosPeças-Canarana-BA",
                    "cliente_codigo": "SantosPeças-Canarana-BA",
                    "numero_serie": "SERIE-01",
                },
                {
                    "data_carga": "2026-05-20",
                    "codigo_recurso": "FTC4300R CS RS/RS M24",
                    "quantidade": 1.0,
                    "presente_no_carreta": "✅",
                    "carga": "V ProdPrópria p Consumo",
                    "cliente": "SantosPeças-Canarana-BA",
                    "cliente_codigo": "SantosPeças-Canarana-BA",
                    "numero_serie": "SERIE-02",
                },
            ],
            "itens_sem_numero_serie": [
                {
                    "sheet_row_index": 9,
                    "data_carga": "2026-05-20",
                    "codigo_recurso": "TANQUE FTC4300R M24",
                    "quantidade": 1.0,
                    "presente_no_carreta": "âœ…",
                    "carga": "V ProdPrÃ³pria p Consumo",
                    "cliente": "SantosPeÃ§as-Canarana-BA",
                    "cliente_codigo": "SantosPeÃ§as-Canarana-BA",
                    "numero_serie": "",
                }
            ],
            "celulas": [{"celula": "CHASSI"}],
        }

        response = self.client.get(
            reverse("cargas:buscar_dados_carreta_planilha"),
            {"data_inicio": "2026-05-20", "data_fim": "2026-05-20"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["cargas"]["cargas"]), 2)
        self.assertEqual(payload["cargas"]["cargas"][0]["numero_serie"], "SERIE-01")
        self.assertEqual(payload["cargas"]["cargas"][1]["numero_serie"], "SERIE-02")
        self.assertEqual(len(payload["cargas"]["itens_sem_numero_serie"]), 1)
        self.assertEqual(payload["cargas"]["itens_sem_numero_serie"][0]["sheet_row_index"], 9)


class ImprimirEtiquetasMontagemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pcp_impressao_montagem", password="123456")
        Profile.objects.create(user=self.user, tipo_acesso="pcp")
        self.client.login(username="pcp_impressao_montagem", password="123456")

    @staticmethod
    def _date(value):
        from datetime import date

        return date.fromisoformat(value)

    @patch("cargas.views.imprimir_ordens_montagem")
    @patch("cargas.views.get_base_carreta")
    def test_impressao_montagem_considera_apenas_recursos_marcados(
        self,
        get_base_carreta_mock,
        imprimir_ordens_montagem_mock,
    ):
        get_base_carreta_mock.return_value = pd.DataFrame(
            [
                {
                    "Recurso": "012345",
                    "Código": "1001",
                    "Peca": "LONGARINA",
                    "Qtde": 2,
                    "Célula": "CHASSI",
                    "Etapa": "Montagem",
                },
                {
                    "Recurso": "067890",
                    "Código": "1002",
                    "Peca": "EIXO",
                    "Qtde": 3,
                    "Célula": "EIXO",
                    "Etapa": "Montagem",
                },
            ]
        )

        carga = CargaLiberada.objects.create(
            data_carga=self._date("2026-05-20"),
            carga_nome="Carga 01",
        )
        versao = CargaLiberadaVersao.objects.create(
            carga_liberada=carga,
            versao=1,
            data_inicio_pesquisa=self._date("2026-05-20"),
            data_fim_pesquisa=self._date("2026-05-20"),
            liberado_por=self.user,
            payload_snapshot={},
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="012345",
            quantidade=2,
            presente_no_carreta="✅",
        )
        CargaLiberadaItem.objects.create(
            carga_versao=versao,
            codigo_recurso="067890",
            quantidade=1,
            presente_no_carreta="✅",
        )

        response = self.client.post(
            reverse("cargas:enviar_etiqueta_impressora_montagem"),
            data=json.dumps(
                {
                    "cargas": [
                        {
                            "nome": "Carga 01",
                            "data_carga": "2026-05-20",
                            "celulas": ["CHASSI", "EIXO"],
                            "recursos": ["012345"],
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        imprimir_ordens_montagem_mock.assert_called_once()

        df_final = imprimir_ordens_montagem_mock.call_args[0][0]
        self.assertEqual(len(df_final), 1)
        self.assertEqual(df_final.iloc[0]["Código"], "1001")
        self.assertEqual(df_final.iloc[0]["Peca"], "LONGARINA")
        self.assertEqual(df_final.iloc[0]["Célula"], "CHASSI")
        self.assertEqual(int(df_final.iloc[0]["Qtde_total"]), 4)


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
