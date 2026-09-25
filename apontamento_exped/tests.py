from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cadastro.models import CarretasExplodidas
from cargas.models import CargaLiberada, CargaLiberadaItem, CargaLiberadaVersao
from apontamento_exped.models import BipagemPacote, Carga, CarretaCarga, Pacote, PendenciasPacote
from apontamento_exped.services import status_bipagem_carga
from apontamento_exped.utils import codigo_barras_pacote, pacote_id_do_codigo_barras
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


class BipagemPacoteTests(TestCase):
    def setUp(self):
        from datetime import date

        from rest_framework.authtoken.models import Token

        from core.models import Profile

        self.user = User.objects.create_user(username="exped_bipagem", password="123456")
        Profile.objects.create(user=self.user, tipo_acesso="operador")
        self.token = Token.objects.create(user=self.user)

        self.carga = Carga.objects.create(
            nome="Carga 10", carga="Carga 01", data_carga=date(2026, 9, 24),
            cliente="Cliente A", stage="bipagem",
        )
        self.outra_carga = Carga.objects.create(
            nome="Carga 11", carga="Carga 02", data_carga=date(2026, 9, 24),
            cliente="Cliente B", stage="bipagem",
        )
        self.pacote_1 = Pacote.objects.create(nome="CLI_A_001", carga=self.carga)
        self.pacote_2 = Pacote.objects.create(nome="CLI_A_002", carga=self.carga)
        self.pacote_outra = Pacote.objects.create(nome="CLI_B_001", carga=self.outra_carga)

    def _bipar(self, codigo, carga=None):
        carga = carga or self.carga
        return self.client.post(
            reverse('expedicao:expedicao_mobile:bipagem_carga', args=[carga.id]),
            {'codigo': codigo},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
        ).json()

    def test_codigo_barras_ida_e_volta(self):
        codigo = codigo_barras_pacote(123)
        self.assertEqual(codigo, 'PK000123')
        self.assertEqual(pacote_id_do_codigo_barras(codigo), 123)
        self.assertEqual(pacote_id_do_codigo_barras(' pk000123 '), 123)
        self.assertIsNone(pacote_id_do_codigo_barras('7891234567890'))
        self.assertIsNone(pacote_id_do_codigo_barras(''))

    def test_bipar_pacote_da_carga(self):
        resposta = self._bipar(codigo_barras_pacote(self.pacote_1.id))

        self.assertEqual(resposta['resultado'], 'ok')
        self.assertEqual(resposta['total_bipados'], 1)
        self.assertFalse(resposta['completo'])
        bipagem = BipagemPacote.objects.get(pacote=self.pacote_1)
        self.assertEqual(bipagem.bipado_por.user, self.user)

    def test_bipar_duas_vezes_nao_duplica(self):
        codigo = codigo_barras_pacote(self.pacote_1.id)
        self._bipar(codigo)
        resposta = self._bipar(codigo)

        self.assertEqual(resposta['resultado'], 'duplicado')
        self.assertEqual(BipagemPacote.objects.filter(pacote=self.pacote_1).count(), 1)

    def test_bipar_pacote_de_outra_carga(self):
        resposta = self._bipar(codigo_barras_pacote(self.pacote_outra.id))

        self.assertEqual(resposta['resultado'], 'outra_carga')
        self.assertFalse(BipagemPacote.objects.exists())

    def test_bipar_codigo_invalido_e_inexistente(self):
        self.assertEqual(self._bipar('7891234567890')['resultado'], 'codigo_invalido')
        self.assertEqual(self._bipar(codigo_barras_pacote(999999))['resultado'], 'nao_encontrado')

    def test_bipar_fora_da_etapa_despachado(self):
        for stage in ('planejamento', 'verificacao', 'despachado'):
            self.carga.stage = stage
            self.carga.save()

            resposta = self._bipar(codigo_barras_pacote(self.pacote_1.id))
            self.assertEqual(resposta['resultado'], 'fora_da_etapa')
        self.assertFalse(BipagemPacote.objects.exists())

    def test_completo_despacha_a_carga_sozinho(self):
        resposta = self._bipar(codigo_barras_pacote(self.pacote_1.id))
        self.assertEqual(resposta['stage'], 'bipagem')

        resposta = self._bipar(codigo_barras_pacote(self.pacote_2.id))
        self.assertTrue(resposta['completo'])
        self.assertEqual(resposta['stage'], 'despachado')
        self.carga.refresh_from_db()
        self.assertEqual(self.carga.stage, 'despachado')
        self.assertIsNotNone(self.carga.data_despachado)

        status = status_bipagem_carga(self.carga)
        self.assertEqual(status['total_bipados'], 2)
        self.assertEqual([p['codigo_barras'] for p in status['pacotes']],
                         [codigo_barras_pacote(self.pacote_1.id), codigo_barras_pacote(self.pacote_2.id)])

    def test_pacotes_travados_na_bipagem(self):
        from apontamento_exped.services import (
            PacoteValidationError, criar_ou_atualizar_pacote, deletar_pacote_service, duplicar_pacote_service,
        )

        with self.assertRaises(PacoteValidationError):
            criar_ou_atualizar_pacote(self.carga, nome_pacote='NOVO')
        with self.assertRaises(PacoteValidationError):
            deletar_pacote_service(self.pacote_1)
        with self.assertRaises(PacoteValidationError):
            duplicar_pacote_service(self.pacote_1)

    def test_desfazer_bipagem(self):
        self._bipar(codigo_barras_pacote(self.pacote_1.id))
        resposta = self.client.delete(
            reverse('expedicao:expedicao_mobile:desfazer_bipagem', args=[self.carga.id, self.pacote_1.id]),
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(BipagemPacote.objects.exists())

    def test_desfazer_bipagem_fora_da_etapa(self):
        self._bipar(codigo_barras_pacote(self.pacote_1.id))
        self.carga.stage = 'despachado'
        self.carga.save()

        resposta = self.client.delete(
            reverse('expedicao:expedicao_mobile:desfazer_bipagem', args=[self.carga.id, self.pacote_1.id]),
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(BipagemPacote.objects.exists())


class AvancarStageTests(TestCase):
    def setUp(self):
        from datetime import date

        from rest_framework.authtoken.models import Token

        from core.models import Profile

        self.user = User.objects.create_user(username="exped_avanco", password="123456")
        Profile.objects.create(user=self.user, tipo_acesso="operador")
        self.token = Token.objects.create(user=self.user)
        self.carga = Carga.objects.create(
            nome="Carga 20", carga="Carga 01", data_carga=date(2026, 9, 25),
            cliente="Cliente A", stage="planejamento",
        )
        self.pacote = Pacote.objects.create(nome="CLI_A_001", carga=self.carga)

    def _avancar(self):
        return self.client.post(
            reverse('expedicao:expedicao_mobile:avancar_stage', args=[self.carga.id]),
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
        )

    def _requisitos(self):
        return self.client.get(
            reverse('expedicao:expedicao_mobile:avancar_stage', args=[self.carga.id]),
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
        ).json()

    def test_planejamento_avanca_para_verificacao(self):
        self.assertTrue(self._requisitos()['pode_avancar'])

        resposta = self._avancar()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['novo_stage'], 'verificacao')

    def test_verificacao_bloqueia_sem_foto(self):
        self.carga.stage = 'verificacao'
        self.carga.save()

        requisitos = self._requisitos()
        self.assertFalse(requisitos['pode_avancar'])
        self.assertIn('CLI_A_001', requisitos['bloqueios'][0])

        resposta = self._avancar()
        self.assertEqual(resposta.status_code, 400)
        self.carga.refresh_from_db()
        self.assertEqual(self.carga.stage, 'verificacao')

    def test_verificacao_com_foto_vai_para_bipagem(self):
        from apontamento_exped.models import ImagemPacote

        self.carga.stage = 'verificacao'
        self.carga.save()
        ImagemPacote.objects.create(pacote=self.pacote, arquivo='imagem_pacote/f.jpg', stage='verificacao')

        resposta = self._avancar()
        self.assertEqual(resposta.status_code, 200)
        self.carga.refresh_from_db()
        self.assertEqual(self.carga.stage, 'bipagem')
        self.assertIsNone(self.carga.data_despachado)

    def test_bipagem_so_avanca_com_tudo_bipado(self):
        self.carga.stage = 'bipagem'
        self.carga.save()

        requisitos = self._requisitos()
        self.assertEqual(requisitos['proximo_stage'], 'despachado')
        self.assertFalse(requisitos['pode_avancar'])
        self.assertIn('0/1', requisitos['bloqueios'][0])
        self.assertEqual(self._avancar().status_code, 400)

        BipagemPacote.objects.create(pacote=self.pacote, data_bipagem=self.carga.data_criacao)
        self.assertEqual(self._avancar().status_code, 200)
        self.carga.refresh_from_db()
        self.assertEqual(self.carga.stage, 'despachado')

    def test_despachado_nao_avanca(self):
        self.carga.stage = 'despachado'
        self.carga.save()

        self.assertIsNone(self._requisitos()['proximo_stage'])
        self.assertEqual(self._avancar().status_code, 400)

    def test_web_usa_mesmas_regras(self):
        self.carga.stage = 'verificacao'
        self.carga.save()
        self.client.force_login(self.user)

        resposta = self.client.post(reverse('expedicao:alterar_stage', args=[self.carga.id]))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('sem foto', resposta.json()['erro'])

    def test_carga_antiga_despachada_agora_continua_na_lista(self):
        from datetime import timedelta

        from django.utils import timezone

        from apontamento_exped.services import listar_cargas_ativas

        antiga = timezone.now() - timedelta(days=60)
        Carga.objects.filter(id=self.carga.id).update(
            stage='despachado', data_criacao=antiga, data_despachado=timezone.now(),
        )
        velha_sem_data = Carga.objects.create(
            nome="Carga velha", carga="Carga 02", cliente="Cliente B", stage="despachado",
        )
        Carga.objects.filter(id=velha_sem_data.id).update(data_criacao=antiga)

        ids = [c['id'] for c in listar_cargas_ativas()]
        self.assertIn(self.carga.id, ids)
        self.assertNotIn(velha_sem_data.id, ids)
