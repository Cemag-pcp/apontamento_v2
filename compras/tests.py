from pathlib import Path

import pandas as pd
from django.conf import settings
from django.test import SimpleTestCase

from compras.services.data_processing import (
    _calcular_datas_projecao,
    _parse_data_entrega,
    get_projecao_para_material,
    processar_material_direto,
)
from compras.services.sugestoes import gerar_sugestoes


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
        self.assertIn("?v=20260618-2", analise)
        self.assertIn("?v=20260618-2", indireto)
        self.assertNotIn("COMPRAS_URGENTE_COM_PEDIDO_LABEL", analise)
        self.assertNotIn("COMPRAS_URGENTE_COM_PEDIDO_LABEL", indireto)
        self.assertNotIn("URGENTE_COM_PEDIDO_LABEL", script)
        self.assertIn("URGENTE_COM_PEDIDO:'<span class=\"compras-badge urgente\"><i class=\"fas fa-triangle-exclamation\"></i> Ped. Atrasado</span>'", script)
        self.assertNotIn("fa-truck", script)

    def test_entrega_atrasada_aplica_somente_na_analise_direta(self):
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
        self.assertNotIn("COMPRAS_EXIBIR_ENTREGA_ATRASADA", indireto)
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
        self.assertNotIn("COMPRAS_GRAFICO_ENRIQUECIDO", indireto)
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
