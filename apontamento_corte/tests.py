from django.test import SimpleTestCase, TestCase
from unittest.mock import patch

from cadastro.models import CarretasExplodidas
from core.models import Ordem, PropriedadesOrdem
from apontamento_corte.models import PecasOrdem

from .views import (
    _dados_carreta_explodida_peca_corte,
    _erro_depositodest_indefinido_corte,
    _item_precisa_transferencia_chapa_corte,
    _resolver_ficha_tecnica_chapa_corte,
    _ordem_precisa_transferencia_chapa_corte,
    _tentar_apontamento_depositodest_processos_alternativos_corte,
    _transferencia_chapa_corte_confirmada,
)


class FakeERPResponse:
    def __init__(self, payload, ok=True, status_code=200, text=''):
        self.payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.payload


class DadosCarretaExplodidaPecaCorteTests(TestCase):
    def test_prefere_registro_com_peso_quando_primeiro_cadastro_esta_sem_peso(self):
        CarretasExplodidas.objects.create(
            codigo_peca='030341',
            descricao_peca='PISO DIREITO [PLATAFORMA - CBHM]',
            mp_peca='MS 2,25 mm',
            peso='',
        )
        registro_com_peso = CarretasExplodidas.objects.create(
            codigo_peca='030341',
            descricao_peca='PISO DIREITO [PLATAFORMA - CBHM]',
            mp_peca='MS 2,25 mm',
            peso='58,7 kg',
        )

        dados_carreta = _dados_carreta_explodida_peca_corte('030341')

        self.assertEqual(dados_carreta, registro_com_peso)

    def test_retorna_primeiro_registro_para_manter_erro_quando_peca_nao_tem_peso(self):
        primeiro_registro = CarretasExplodidas.objects.create(
            codigo_peca='030341',
            descricao_peca='PISO DIREITO [PLATAFORMA - CBHM]',
            mp_peca='MS 2,25 mm',
            peso='',
        )
        CarretasExplodidas.objects.create(
            codigo_peca='030341',
            descricao_peca='PISO DIREITO [PLATAFORMA - CBHM]',
            mp_peca='MS 2,25 mm',
            peso=None,
        )

        dados_carreta = _dados_carreta_explodida_peca_corte('030341')

        self.assertEqual(dados_carreta, primeiro_registro)


class FallbackProcessoDepositoDestCorteTests(SimpleTestCase):
    def test_detecta_erro_depositodest_undefined(self):
        erro = (
            'Error: Não é possível atribuir valor undefined a um campo do DataSet. '
            'Fieldname: "DEPOSITODEST"'
        )

        self.assertTrue(_erro_depositodest_indefinido_corte(erro))

    @patch('apontamento_corte.views._post_apontamento_erp_corte')
    def test_tenta_processos_alternativos_sem_repetir_processo_original(self, mock_post):
        payload = {
            'id': 'corte-item-117896',
            'processo': 'S C Plasma',
            'produzido': 4,
        }

        def responder(payload_enviado):
            if payload_enviado['processo'] == 'S C Laser':
                return FakeERPResponse({'status': 'success', 'chaveProducao': 'CHAVE-LASER'})
            return FakeERPResponse({
                'status': 'error',
                'description': 'DEPOSITODEST undefined',
            })

        mock_post.side_effect = responder

        payload_final, retorno_final, tentativas = (
            _tentar_apontamento_depositodest_processos_alternativos_corte(payload)
        )

        processos_tentados = [call.args[0]['processo'] for call in mock_post.call_args_list]
        self.assertNotIn('S C Plasma', processos_tentados)
        self.assertIn('S C Laser', processos_tentados)
        self.assertEqual(payload['processo'], 'S C Plasma')
        self.assertEqual(payload_final['processo'], 'S C Laser')
        self.assertEqual(retorno_final['status'], 'success')
        self.assertTrue(tentativas)


class TransferenciaChapaConfirmadaCorteTests(SimpleTestCase):
    def test_confirma_apenas_transferencia_com_sucesso_ou_ja_transferida(self):
        self.assertTrue(_transferencia_chapa_corte_confirmada({'status': 'sucesso'}))
        self.assertTrue(_transferencia_chapa_corte_confirmada({'status': 'erro', 'ja_transferida': True}))
        self.assertFalse(_transferencia_chapa_corte_confirmada({'status': 'erro'}))
        self.assertFalse(_transferencia_chapa_corte_confirmada({'status': 'ignorada'}))
        self.assertFalse(_transferencia_chapa_corte_confirmada(None))

    def test_ordem_precisa_transferencia_quando_tem_item_e_chapa_valida(self):
        dados_chapa = {'encontrou_chapa': True, 'codigo': '120203'}

        self.assertTrue(_ordem_precisa_transferencia_chapa_corte([object()], dados_chapa))
        self.assertFalse(_ordem_precisa_transferencia_chapa_corte([], dados_chapa))
        self.assertFalse(_ordem_precisa_transferencia_chapa_corte([object()], {'encontrou_chapa': False, 'codigo': '120203'}))
        self.assertFalse(_ordem_precisa_transferencia_chapa_corte([object()], {'encontrou_chapa': True, 'codigo': ''}))


class RegraTransferenciaChapaCorteTests(TestCase):
    def criar_item(self, codigo_chapa_ordem, materia_peca):
        ordem = Ordem.objects.create(
            ordem=12345,
            grupo_maquina='plasma',
            status_atual='finalizada',
        )
        PropriedadesOrdem.objects.create(
            ordem=ordem,
            descricao_mp=f'{codigo_chapa_ordem} - CHAPA DA ORDEM',
            quantidade=1,
        )
        item = PecasOrdem.objects.create(
            ordem=ordem,
            peca='030341 - PISO DIREITO',
            qtd_planejada=1,
            qtd_boa=1,
        )
        CarretasExplodidas.objects.create(
            codigo_peca='030341',
            descricao_peca='PISO DIREITO',
            mp_peca=materia_peca,
            peso='1,0 kg',
        )
        return item

    def test_nao_exige_transferencia_quando_codigo_da_chapa_e_igual(self):
        item = self.criar_item('012345', '012345 - MP DA PECA')

        precisa_transferencia = _item_precisa_transferencia_chapa_corte(item, '012345')
        peca_valida, aviso, ficha_tecnica = _resolver_ficha_tecnica_chapa_corte(
            item,
            transferencia=None,
            codigo_chapa_ordem='012345',
        )

        self.assertFalse(precisa_transferencia)
        self.assertTrue(peca_valida)
        self.assertEqual(aviso, '')
        self.assertIsNone(ficha_tecnica)

    def test_exige_transferencia_quando_codigo_da_chapa_e_diferente(self):
        item = self.criar_item('099999', '012345 - MP DA PECA')

        precisa_transferencia = _item_precisa_transferencia_chapa_corte(item, '099999')
        peca_valida, aviso, ficha_tecnica = _resolver_ficha_tecnica_chapa_corte(
            item,
            transferencia=None,
            codigo_chapa_ordem='099999',
        )

        self.assertTrue(precisa_transferencia)
        self.assertFalse(peca_valida)
        self.assertIn('Transfira a chapa antes de apontar', aviso)
        self.assertIsNone(ficha_tecnica)

    def test_nao_exige_transferencia_quando_materia_prima_nao_tem_codigo(self):
        item = self.criar_item('099999', 'MS 4,75 mm')

        precisa_transferencia = _item_precisa_transferencia_chapa_corte(item, '099999')
        peca_valida, aviso, ficha_tecnica = _resolver_ficha_tecnica_chapa_corte(
            item,
            transferencia=None,
            codigo_chapa_ordem='099999',
        )

        self.assertFalse(precisa_transferencia)
        self.assertTrue(peca_valida)
        self.assertEqual(aviso, '')
        self.assertIsNone(ficha_tecnica)
