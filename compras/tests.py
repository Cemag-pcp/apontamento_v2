from pathlib import Path

import pandas as pd
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from unittest.mock import Mock, patch

from compras.services.data_processing import (
    _calcular_datas_projecao,
    _parse_data_entrega,
    get_projecao_para_material,
    processar_material_direto,
)
from compras.services.sugestoes import gerar_sugestoes
from compras import views as compras_views


class ComprasScrollSuperiorTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compras_dir = Path(settings.BASE_DIR) / "compras"

    def test_scroll_superior_existe_apenas_na_analise_direta(self):
        analise = (
            self.compras_dir / "templates" / "compras" / "analise.html"
        ).read_text(encoding="utf-8")
        indireto = (
            self.compras_dir / "templates" / "compras" / "mat_indireto.html"
        ).read_text(encoding="utf-8")

        self.assertIn('id="comprasTableScrollTop"', analise)
        self.assertIn('id="comprasTableScrollTopContent"', analise)
        self.assertNotIn('id="comprasTableScrollTop"', indireto)

    def test_javascript_sincroniza_e_redimensiona_scroll_superior(self):
        script = (
            self.compras_dir / "static" / "js" / "compras.js"
        ).read_text(encoding="utf-8")

        self.assertIn("tableWrap.scrollLeft = scrollTop.scrollLeft", script)
        self.assertIn("scrollTop.scrollLeft = tableWrap.scrollLeft", script)
        self.assertIn("new ResizeObserver", script)
        self.assertIn("possuiOverflowHorizontal", script)
        self.assertIn("agendarAtualizacaoScrollSuperior();", script)

    def test_urgente_com_pedido_usa_label_pedido_atrasado(self):
        analise = (
            self.compras_dir / "templates" / "compras" / "analise.html"
        ).read_text(encoding="utf-8")
        indireto = (
            self.compras_dir / "templates" / "compras" / "mat_indireto.html"
        ).read_text(encoding="utf-8")
        script = (
            self.compras_dir / "static" / "js" / "compras.js"
        ).read_text(encoding="utf-8")

        self.assertIn('<option value="URGENTE_COM_PEDIDO">🔴 Ped. Atrasado</option>', analise)
        self.assertIn('<option value="URGENTE_COM_PEDIDO">🔴 Ped. Atrasado</option>', indireto)
        self.assertNotIn("Aguardando chegar", analise)
        self.assertNotIn("Aguardando chegar", indireto)
        self.assertIn("?v=20260618-5", analise)
        self.assertIn("?v=20260618-5", indireto)
        self.assertNotIn("COMPRAS_URGENTE_COM_PEDIDO_LABEL", analise)
        self.assertNotIn("COMPRAS_URGENTE_COM_PEDIDO_LABEL", indireto)
        self.assertNotIn("URGENTE_COM_PEDIDO_LABEL", script)
        self.assertIn("URGENTE_COM_PEDIDO:'<span class=\"compras-badge urgente\"><i class=\"fas fa-triangle-exclamation\"></i> Ped. Atrasado</span>'", script)
        self.assertNotIn("fa-truck", script)

    def test_entrega_atrasada_aplica_nas_duas_telas(self):
        analise = (
            self.compras_dir / "templates" / "compras" / "analise.html"
        ).read_text(encoding="utf-8")
        indireto = (
            self.compras_dir / "templates" / "compras" / "mat_indireto.html"
        ).read_text(encoding="utf-8")
        script = (
            self.compras_dir / "static" / "js" / "compras.js"
        ).read_text(encoding="utf-8")

        self.assertIn("window.COMPRAS_EXIBIR_ENTREGA_ATRASADA = true", analise)
        self.assertIn("window.COMPRAS_EXIBIR_ENTREGA_ATRASADA = true", indireto)
        self.assertIn("formatarDataProximaCompra(m)", script)
        self.assertIn("formatarSituacao(m)", script)
        self.assertIn("dataCompraEstaAtrasada(material)", script)
        self.assertIn("proximaCompraEstaAtrasada(material)", script)
        self.assertIn("entregaPedidoEstaAtrasada(material)", script)
        self.assertIn("pedidos_atrasados_count", script)
        self.assertIn('${material.data_compra}', script)
        self.assertIn("compras-entrega-atrasada", script)
        self.assertIn("compras-proxima-compra-curta", script)
        self.assertIn("situacao-badges", script)
        self.assertIn('<div class="situacao-badges">${formatarSituacao(m)}</div>', script)
        self.assertIn("URGENTE:           '<span class=\"compras-badge urgente\"><i class=\"fas fa-triangle-exclamation\"></i> Ped. Atrasado</span>'", script)
        self.assertNotIn("fa-arrow-down\"></i> Ped. Atrasado", script)
        self.assertIn("calendar-xmark", script)
        self.assertIn("return -Infinity", script)
        self.assertIn(
            "['PEDIDO_ATRASADO', 'URGENTE', 'URGENTE_COM_PEDIDO'].includes(material.flag_urgencia)",
            script,
        )
        self.assertIn("dataCompra < hoje.getTime()", script)
        self.assertIn(
            "chaveOrdenacaoDataCompra(a) - chaveOrdenacaoDataCompra(b)",
            script,
        )

    def test_filtro_considerar_pedidos_existe_nas_duas_telas(self):
        analise = (
            self.compras_dir / "templates" / "compras" / "analise.html"
        ).read_text(encoding="utf-8")
        indireto = (
            self.compras_dir / "templates" / "compras" / "mat_indireto.html"
        ).read_text(encoding="utf-8")
        script = (
            self.compras_dir / "static" / "js" / "compras.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Considerar Pedidos", analise)
        self.assertIn('id="filtroConsiderarPedidos"', analise)
        self.assertIn('<option value="0" selected>Não</option>', analise)
        self.assertIn('<option value="1">Sim</option>', analise)
        self.assertIn("Considerar Pedidos", indireto)
        self.assertIn('id="filtroConsiderarPedidos"', indireto)
        self.assertIn('<option value="0" selected>Não</option>', indireto)
        self.assertIn('<option value="1">Sim</option>', indireto)
        self.assertIn("considerar_pedidos", script)
        self.assertIn("considerarPedidos ? considerarPedidos.value : '0'", script)
        self.assertIn("filtroConsiderarPedidos.addEventListener('change'", script)
        self.assertIn("descricaoAtualProjecao", script)
        self.assertIn("modalAberto && codigoAtualProjecao", script)
        self.assertIn("carregarProjecao(codigoAtualProjecao, descricaoAtualProjecao)", script)
        self.assertIn("check_only: '1'", script)
        self.assertIn("considerar_pedidos: getParams().considerar_pedidos", script)

    def test_grafico_enriquecido_tem_todas_as_bandeiras(self):
        analise = (
            self.compras_dir / "templates" / "compras" / "analise.html"
        ).read_text(encoding="utf-8")
        indireto = (
            self.compras_dir / "templates" / "compras" / "mat_indireto.html"
        ).read_text(encoding="utf-8")
        script = (
            self.compras_dir / "static" / "js" / "compras.js"
        ).read_text(encoding="utf-8")

        self.assertIn("window.COMPRAS_GRAFICO_ENRIQUECIDO = true", analise)
        self.assertIn("window.COMPRAS_GRAFICO_ENRIQUECIDO = true", indireto)
        for tipo in (
            "hoje",
            "entrega_prevista",
            "entrega_atrasada",
            "proxima_compra",
            "estoque_minimo",
            "estoque_zero",
        ):
            self.assertIn(f"{tipo}:", script)
        self.assertIn("renderPlotlyEnriquecido(data)", script)
        self.assertIn("sugestao-indicadores", script)


class ComprasConsiderarPedidosApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = Mock(is_authenticated=True)
        self.resultado = {
            "materiais": [
                {
                    "codigo": "292254",
                    "descricao": "Material teste",
                    "grupo": "Grupo",
                    "flag_urgencia": "PRAZO_OK",
                }
            ],
            "codigos": ["292254"],
            "grupos": ["Grupo"],
            "df": pd.DataFrame([{"codigo": "292254"}]),
            "df_pedidos": pd.DataFrame(columns=["codigo", "data_entrega", "qde_ped_corrigido"]),
        }

    def _request(self, path):
        request = self.factory.get(path)
        request.user = self.user
        return request

    @patch("compras.views.get_pedidos_df")
    @patch("compras.views.get_simulacao_df")
    @patch("compras.views.processar_material_direto")
    def test_material_direto_nao_considera_pedidos_por_padrao(
        self,
        mock_processar,
        mock_simulacao,
        mock_pedidos,
    ):
        mock_simulacao.return_value = pd.DataFrame()
        mock_pedidos.return_value = pd.DataFrame()
        mock_processar.return_value = self.resultado

        response = compras_views.api_material_direto(self._request("/compras/api/material-direto/"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(mock_processar.call_args.kwargs["considerar_pedido_pendente_como_recebido"])

    @patch("compras.views.gerar_sugestoes")
    @patch("compras.views.get_projecao_para_material")
    @patch("compras.views.get_pedidos_df")
    @patch("compras.views.get_simulacao_df")
    @patch("compras.views.processar_material_direto")
    def test_projecao_considera_pedidos_quando_parametro_igual_um(
        self,
        mock_processar,
        mock_simulacao,
        mock_pedidos,
        mock_projecao,
        mock_sugestoes,
    ):
        mock_simulacao.return_value = pd.DataFrame()
        mock_pedidos.return_value = pd.DataFrame()
        mock_processar.return_value = self.resultado
        mock_projecao.return_value = {"codigo": "292254"}
        mock_sugestoes.return_value = []

        response = compras_views.api_projecao(
            self._request("/compras/api/projecao/?codigo=292254&considerar_pedidos=1")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_processar.call_args.kwargs["considerar_pedido_pendente_como_recebido"])
        self.assertTrue(mock_projecao.call_args.kwargs["considerar_pedido_pendente_como_recebido"])

    @patch("compras.views.check_cache")
    @patch("compras.views.get_projecao_para_material")
    @patch("compras.views.get_pedidos_df")
    @patch("compras.views.get_simulacao_df")
    @patch("compras.views.processar_material_direto")
    def test_analise_ia_direta_considera_pedidos_quando_parametro_igual_um(
        self,
        mock_processar,
        mock_simulacao,
        mock_pedidos,
        mock_projecao,
        mock_check_cache,
    ):
        mock_simulacao.return_value = pd.DataFrame()
        mock_pedidos.return_value = pd.DataFrame()
        mock_processar.return_value = self.resultado
        mock_projecao.return_value = {"codigo": "292254"}
        mock_check_cache.return_value = None

        response = compras_views.api_analise_ia(
            self._request("/compras/api/analise-ia/?codigo=292254&considerar_pedidos=1&check_only=1")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_processar.call_args.kwargs["considerar_pedido_pendente_como_recebido"])
        self.assertTrue(mock_projecao.call_args.kwargs["considerar_pedido_pendente_como_recebido"])

    @patch("compras.views.get_mat_indireto_pedidos_df")
    @patch("compras.views.get_mat_indireto_simulacao_df")
    @patch("compras.views.processar_material_direto")
    def test_material_indireto_nao_considera_pedidos_por_padrao(
        self,
        mock_processar,
        mock_simulacao,
        mock_pedidos,
    ):
        mock_simulacao.return_value = pd.DataFrame()
        mock_pedidos.return_value = pd.DataFrame()
        mock_processar.return_value = self.resultado

        response = compras_views.api_material_indireto(
            self._request("/compras/mat_indireto/api/material-direto/")
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(mock_processar.call_args.kwargs["considerar_pedido_pendente_como_recebido"])

    @patch("compras.views.gerar_sugestoes")
    @patch("compras.views.get_projecao_para_material")
    @patch("compras.views.get_mat_indireto_pedidos_df")
    @patch("compras.views.get_mat_indireto_simulacao_df")
    @patch("compras.views.processar_material_direto")
    def test_projecao_indireta_considera_pedidos_quando_parametro_igual_um(
        self,
        mock_processar,
        mock_simulacao,
        mock_pedidos,
        mock_projecao,
        mock_sugestoes,
    ):
        mock_simulacao.return_value = pd.DataFrame()
        mock_pedidos.return_value = pd.DataFrame()
        mock_processar.return_value = self.resultado
        mock_projecao.return_value = {"codigo": "292254"}
        mock_sugestoes.return_value = []

        response = compras_views.api_projecao_indireto(
            self._request("/compras/mat_indireto/api/projecao/?codigo=292254&considerar_pedidos=1")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_processar.call_args.kwargs["considerar_pedido_pendente_como_recebido"])
        self.assertTrue(mock_projecao.call_args.kwargs["considerar_pedido_pendente_como_recebido"])

    @patch("compras.views.check_cache")
    @patch("compras.views.get_projecao_para_material")
    @patch("compras.views.get_mat_indireto_pedidos_df")
    @patch("compras.views.get_mat_indireto_simulacao_df")
    @patch("compras.views.processar_material_direto")
    def test_analise_ia_indireta_considera_pedidos_quando_parametro_igual_um(
        self,
        mock_processar,
        mock_simulacao,
        mock_pedidos,
        mock_projecao,
        mock_check_cache,
    ):
        mock_simulacao.return_value = pd.DataFrame()
        mock_pedidos.return_value = pd.DataFrame()
        mock_processar.return_value = self.resultado
        mock_projecao.return_value = {"codigo": "292254"}
        mock_check_cache.return_value = None

        response = compras_views.api_analise_ia_indireto(
            self._request("/compras/mat_indireto/api/analise-ia/?codigo=292254&considerar_pedidos=1&check_only=1")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_processar.call_args.kwargs["considerar_pedido_pendente_como_recebido"])
        self.assertTrue(mock_projecao.call_args.kwargs["considerar_pedido_pendente_como_recebido"])


class ComprasCalculoPedidoPendenteTests(SimpleTestCase):
    def setUp(self):
        self.row = pd.Series(
            {
                "codigo": "292254",
                "estoque_almox_central": 4,
                "estoque_almox": 4,
                "estoque_minimo": 2.74,
                "consumo_diario": 0.275,
                "dias_ressupr": 35,
                "ped_compras_pendente": 20,
            }
        )

    def test_pedido_nao_atrasado_e_considerado_como_recebido(self):
        pedidos = pd.DataFrame(
            columns=["codigo", "data_entrega", "qde_ped_corrigido"]
        )

        calculo_atual = _calcular_datas_projecao(self.row, pedidos)
        calculo_recalculado = _calcular_datas_projecao(
            self.row,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertLess(calculo_atual["dias_ate_data_compra"], 0)
        self.assertGreater(calculo_recalculado["dias_ate_data_compra"], 0)

    def test_pedido_futuro_nao_e_somado_duas_vezes(self):
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "292254",
                    "data_entrega": pd.Timestamp.now().normalize()
                    + pd.Timedelta(days=5),
                    "qde_ped_corrigido": 20,
                }
            ]
        )
        sem_detalhe = pedidos.iloc[0:0]

        com_entrega = _calcular_datas_projecao(
            self.row,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )
        sem_entrega = _calcular_datas_projecao(
            self.row,
            sem_detalhe,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertEqual(com_entrega, sem_entrega)

    def test_pedido_atrasado_nao_e_considerado_como_recebido(self):
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "292254",
                    "data_entrega": pd.Timestamp.now().normalize()
                    - pd.Timedelta(days=1),
                    "qde_ped_corrigido": 20,
                }
            ]
        )

        resultado = _calcular_datas_projecao(
            self.row,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertLess(resultado["dias_ate_data_compra"], 0)

    def test_estoque_minimo_nao_espera_entrega_futura_para_ser_marcado(self):
        row = pd.Series(
            {
                "codigo": "112203",
                "estoque_almox_central": 527,
                "estoque_almox": 527,
                "estoque_minimo": 684.84,
                "consumo_diario": 68.484,
                "dias_ressupr": 20,
                "ped_compras_pendente": 2160,
            }
        )
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "112203",
                    "data_entrega": pd.Timestamp.now().normalize()
                    + pd.Timedelta(days=34),
                    "qde_ped_corrigido": 2160,
                }
            ]
        )

        resultado = _calcular_datas_projecao(
            row,
            pedidos,
            considerar_pedido_pendente_como_recebido=False,
        )

        self.assertLessEqual(
            resultado["data_estoque_minimo"],
            resultado["data_estoque_zero"],
        )
        self.assertLess(resultado["dias_ate_data_compra"], 0)


class ComprasParseDataEntregaTests(SimpleTestCase):
    def test_parse_aceita_datas_mistas_da_planilha(self):
        valores = pd.Series(["03/07/2026", "11/09/26", "22/06/26"])

        datas = valores.apply(_parse_data_entrega)

        self.assertEqual(datas.iloc[0], pd.Timestamp("2026-07-03"))
        self.assertEqual(datas.iloc[1], pd.Timestamp("2026-09-11"))
        self.assertEqual(datas.iloc[2], pd.Timestamp("2026-06-22"))


class ComprasProjecaoEnriquecidaTests(SimpleTestCase):
    def setUp(self):
        hoje = pd.Timestamp.now().normalize()
        self.df = pd.DataFrame(
            [
                {
                    "codigo": "292254",
                    "descricao": 'VALVULA DE GAVETA 2"',
                    "estoque_almox_central": 4,
                    "estoque_almox": 4,
                    "estoque_minimo": 2.74,
                    "consumo_diario": 0.275,
                    "dias_ressupr": 35,
                    "ped_compras_pendente": 20,
                    "dias_ate_data_compra": 41,
                    "data_compra": (hoje + pd.Timedelta(days=59)).date(),
                    "data_estoque_minimo": (hoje + pd.Timedelta(days=109)).date(),
                    "data_estoque_zero": (hoje + pd.Timedelta(days=123)).date(),
                    "flag_urgencia": "PRAZO_OK",
                }
            ]
        )

    def test_pedido_sem_data_entra_no_estoque_e_gera_alerta_sem_bandeira(self):
        pedidos = pd.DataFrame(
            columns=["codigo", "data_entrega", "qde_ped_corrigido"]
        )

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertEqual(projecao["estoque_fisico"], 4)
        self.assertEqual(projecao["estoque_projetado"], 24)
        self.assertEqual(projecao["pedidos_sem_data_count"], 1)
        self.assertEqual(projecao["ped_compras_sem_data"], 20)
        tipos = {evento["tipo"] for evento in projecao["eventos_grafico"]}
        self.assertNotIn("entrega_prevista", tipos)
        self.assertIn("hoje", tipos)
        self.assertIn("proxima_compra", tipos)
        self.assertIn("estoque_minimo", tipos)
        self.assertIn("estoque_zero", tipos)

    def test_datas_do_grafico_sao_recalculadas_pelo_parametro_considerar_pedidos(self):
        pedidos = pd.DataFrame(
            columns=["codigo", "data_entrega", "qde_ped_corrigido"]
        )
        self.df.loc[0, "data_compra"] = pd.Timestamp("2000-01-03").date()
        self.df.loc[0, "data_estoque_minimo"] = pd.Timestamp("2000-02-01").date()
        self.df.loc[0, "data_estoque_zero"] = pd.Timestamp("2000-03-01").date()

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )
        esperado = _calcular_datas_projecao(
            self.df.iloc[0],
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )
        eventos = {
            evento["tipo"]: evento
            for evento in projecao["eventos_grafico"]
        }

        self.assertEqual(projecao["data_compra"], esperado["data_compra"].strftime("%d/%m/%Y"))
        self.assertEqual(projecao["data_estoque_minimo"], esperado["data_estoque_minimo"].strftime("%Y-%m-%d"))
        self.assertEqual(projecao["data_estoque_zero"], esperado["data_estoque_zero"].strftime("%d/%m/%Y"))
        self.assertEqual(eventos["proxima_compra"]["data"], esperado["data_compra"].strftime("%Y-%m-%d"))
        self.assertEqual(eventos["estoque_minimo"]["data"], esperado["data_estoque_minimo"].strftime("%Y-%m-%d"))
        self.assertEqual(eventos["estoque_zero"]["data"], esperado["data_estoque_zero"].strftime("%Y-%m-%d"))

    def test_pedido_futuro_gera_bandeira_sem_duplicar_estoque(self):
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "292254",
                    "data_entrega": pd.Timestamp.now().normalize()
                    + pd.Timedelta(days=5),
                    "qde_ped_corrigido": 20,
                }
            ]
        )

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertEqual(projecao["estoque_projetado"], 24)
        self.assertEqual(projecao["serie_real"]["estoques"][0], 24)
        self.assertEqual(projecao["ped_compras_sem_data"], 0)
        eventos = [
            evento
            for evento in projecao["eventos_grafico"]
            if evento["tipo"] == "entrega_prevista"
        ]
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["quantidade"], 20)
        self.assertEqual(eventos[0]["titulo"], "Primeira Entrega")
        self.assertIn("Data da entrega:", eventos[0]["descricao"])

    def test_multiplas_entregas_previstas_recebem_titulo_ordinal(self):
        hoje = pd.Timestamp.now().normalize()
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "292254",
                    "data_entrega": hoje + pd.Timedelta(days=5),
                    "qde_ped_corrigido": 30,
                },
                {
                    "codigo": "292254",
                    "data_entrega": hoje + pd.Timedelta(days=10),
                    "qde_ped_corrigido": 25,
                },
                {
                    "codigo": "292254",
                    "data_entrega": hoje + pd.Timedelta(days=15),
                    "qde_ped_corrigido": 25,
                },
                {
                    "codigo": "292254",
                    "data_entrega": hoje + pd.Timedelta(days=20),
                    "qde_ped_corrigido": 25,
                },
            ]
        )
        self.df.loc[0, "ped_compras_pendente"] = 105

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        eventos = [
            evento
            for evento in projecao["eventos_grafico"]
            if evento["tipo"] == "entrega_prevista"
        ]

        self.assertEqual(
            [evento["titulo"] for evento in eventos],
            ["Primeira Entrega", "Segunda Entrega", "Terceira Entrega", "Quarta Entrega"],
        )
        self.assertTrue(all("Data da entrega:" in evento["descricao"] for evento in eventos))

    def test_pedido_com_data_entrega_nao_gera_alerta_sem_data(self):
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "292254.0 ",
                    "data_entrega": pd.to_datetime("22/06/26", dayfirst=True),
                    "qde_ped_corrigido": 20,
                }
            ]
        )

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertEqual(projecao["pedidos_sem_data_count"], 0)
        self.assertEqual(projecao["ped_compras_sem_data"], 0)

    def test_tooltips_de_estoque_minimo_e_ruptura_incluem_datas(self):
        pedidos = pd.DataFrame(
            columns=["codigo", "data_entrega", "qde_ped_corrigido"]
        )

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )
        eventos = {
            evento["tipo"]: evento
            for evento in projecao["eventos_grafico"]
        }

        self.assertIn("Data para próxima compra:", eventos["proxima_compra"]["descricao"])
        self.assertIn("Data do estoque mínimo:", eventos["estoque_minimo"]["descricao"])
        self.assertIn("Data da ruptura de estoque:", eventos["estoque_zero"]["descricao"])

    def test_pedido_atrasado_nao_aumenta_estoque_e_gera_bandeira(self):
        pedidos = pd.DataFrame(
            [
                {
                    "codigo": "292254",
                    "data_entrega": pd.Timestamp.now().normalize()
                    - pd.Timedelta(days=1),
                    "qde_ped_corrigido": 20,
                }
            ]
        )

        projecao = get_projecao_para_material(
            "292254",
            self.df,
            pedidos,
            considerar_pedido_pendente_como_recebido=True,
        )

        self.assertEqual(projecao["estoque_projetado"], 4)
        self.assertEqual(projecao["ped_compras_atrasado"], 20)
        self.assertIn(
            "entrega_atrasada",
            {evento["tipo"] for evento in projecao["eventos_grafico"]},
        )
        evento_atrasado = next(
            evento
            for evento in projecao["eventos_grafico"]
            if evento["tipo"] == "entrega_atrasada"
        )
        self.assertIn("Data prevista da entrega:", evento_atrasado["descricao"])

    def test_entrega_atrasada_nao_classifica_pedido_com_compra_futura_como_atrasado(self):
        simulacao = pd.DataFrame(
            [
                {
                    "Código": "999999",
                    "Descrição": "MATERIAL TESTE",
                    "Média 3M": "0",
                    "Cons Mes Anterior": "0",
                    "Simulado Pend Vendas": "0",
                    "Est.Almox Central": "200",
                    "Est. Produção": "0",
                    "Estoque Total": "200",
                    "Ped.Compras Pendente": "10",
                    "Prev Con Mov Est(CMM)": "20",
                    "SIMULACAO / (F.Pend/Fat.MM)": "0",
                    "DEE - Dias Em Est.": "0",
                    "Dias Ressupr": "10",
                    "Dias de seg.": "10",
                    "Estoque Mínimo": "10",
                }
            ]
        )
        pedidos = pd.DataFrame(
            [
                {
                    "Recurso": "999999 - MATERIAL TESTE",
                    "Data Entrega": (
                        pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
                    ).strftime("%d/%m/%y"),
                    "Qde Ped": "10,00",
                }
            ]
        )

        resultado = processar_material_direto(
            simulacao,
            pedidos,
            skip_first_row=False,
            considerar_pedido_pendente_como_recebido=True,
        )
        material = resultado["materiais"][0]

        self.assertNotEqual(material["flag_urgencia"], "PEDIDO_ATRASADO")
        self.assertEqual(material["pedidos_atrasados_count"], 1)
        self.assertGreater(material["dias_ate_data_compra"], 0)

    def test_sugestoes_enriquecidas_retornam_tres_blocos(self):
        projecao = {
            "estoque_fisico": 4,
            "estoque_projetado": 24,
            "estoque_minimo": 2.74,
            "consumo_diario": 0.275,
            "ped_compras": 20,
            "pedidos_atrasados_count": 0,
            "pedidos_previstos_count": 0,
            "pedidos_sem_data_count": 1,
            "ped_compras_sem_data": 20,
            "dias_ate_data_compra": 41,
            "dias_ressupr": 35,
            "data_compra": "10/08/2026",
            "data_estoque_minimo": "2026-09-29",
            "data_estoque_zero": "13/10/2026",
        }

        sugestoes = gerar_sugestoes(projecao, formato_enriquecido=True)

        self.assertEqual(len(sugestoes), 3)
        self.assertEqual(sugestoes[0]["tipo"], "resumo")
        self.assertEqual(len(sugestoes[0]["indicadores"]), 6)
        self.assertIn("sem data de entrega", sugestoes[1]["mensagem"])
        self.assertEqual(sugestoes[2]["tipo"], "acao")

    def test_sugestao_informa_quando_pedidos_nao_sao_considerados(self):
        projecao = {
            "estoque_fisico": 527,
            "estoque_projetado": 527,
            "estoque_minimo": 684.84,
            "consumo_diario": 68.484,
            "ped_compras": 2160,
            "considerar_pedidos": False,
            "pedidos_atrasados_count": 0,
            "pedidos_previstos_count": 1,
            "pedidos_sem_data_count": 0,
            "dias_ate_data_compra": -15,
            "dias_ressupr": 20,
            "data_compra": "20/05/2026",
            "data_estoque_minimo": "2026-06-18",
            "data_estoque_zero": "29/06/2026",
        }

        sugestoes = gerar_sugestoes(projecao, formato_enriquecido=True)

        self.assertIn("apenas o estoque físico", sugestoes[0]["mensagem"])
