from django.test import TestCase

from cadastro.models import CarretasExplodidas

from .views import _dados_carreta_explodida_peca_corte


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
