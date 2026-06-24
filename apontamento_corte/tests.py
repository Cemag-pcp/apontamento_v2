from django.test import TestCase

from cadastro.models import CarretasExplodidas
from core.models import Ordem, PropriedadesOrdem
from apontamento_corte.models import PecasOrdem

from .views import (
    _dados_carreta_explodida_peca_corte,
    _item_precisa_transferencia_chapa_corte,
    _resolver_ficha_tecnica_chapa_corte,
)


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
