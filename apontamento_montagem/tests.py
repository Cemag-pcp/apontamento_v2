from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from apontamento_montagem.models import PecasOrdem
from cadastro.models import Maquina, Operador, Setor
from core.models import Ordem, OrdemProcesso


class ApiTemposTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setor = Setor.objects.create(nome='montagem')
        cls.maquina_a = Maquina.objects.create(nome='Linha A', setor=cls.setor, tipo='maquina')
        cls.maquina_b = Maquina.objects.create(nome='Linha B', setor=cls.setor, tipo='maquina')

        cls.ordens = []
        base_time = now() - timedelta(days=4)

        for idx in range(3):
            ordem = Ordem.objects.create(
                ordem=100 + idx,
                grupo_maquina='montagem',
                maquina=cls.maquina_a if idx < 2 else cls.maquina_b,
                status_atual='finalizada' if idx != 1 else 'iniciada',
                data_carga=(base_time + timedelta(days=idx)).date(),
            )
            cls.ordens.append(ordem)

            processo = OrdemProcesso.objects.create(
                ordem=ordem,
                status='finalizada' if idx != 1 else 'iniciada',
                data_inicio=base_time + timedelta(days=idx, hours=idx),
                data_fim=base_time + timedelta(days=idx, hours=idx + 1),
            )

            PecasOrdem.objects.create(
                ordem=ordem,
                peca=f"0{idx + 1}2345 - Conjunto {idx}",
                qtd_planejada=10 + idx,
                qtd_boa=5 + idx,
                processo_ordem=processo,
            )

        cls.url = reverse('montagem:api_tempos')

    def test_returns_paginated_payload_by_default(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['page'], 1)
        self.assertEqual(payload['limit'], 100)
        self.assertEqual(payload['total'], 3)
        self.assertFalse(payload['has_next'])
        self.assertEqual(len(payload['items']), 3)
        self.assertIn('codigo', payload['items'][0])
        self.assertIn('descricao', payload['items'][0])

    def test_clamps_limit_to_maximum(self):
        response = self.client.get(self.url, {'limit': 9999})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['limit'], 500)

    def test_filters_by_ordem(self):
        response = self.client.get(self.url, {'ordem': self.ordens[1].ordem})

        self.assertEqual(response.status_code, 200)
        items = response.json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['ordem'], self.ordens[1].ordem)

    def test_filters_by_maquina(self):
        response = self.client.get(self.url, {'maquina': 'Linha B'})

        self.assertEqual(response.status_code, 200)
        items = response.json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['celula'], 'Linha B')

    def test_filters_by_status(self):
        response = self.client.get(self.url, {'status': 'iniciada'})

        self.assertEqual(response.status_code, 200)
        items = response.json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['status'], 'iniciada')

    def test_filters_by_date_range(self):
        target_date = self.ordens[1].data_carga.isoformat()
        response = self.client.get(
            self.url,
            {'data_inicio': target_date, 'data_fim': target_date}
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['data_carga'], target_date)

    def test_invalid_date_returns_400(self):
        response = self.client.get(self.url, {'data_inicio': '24/03/2026'})

        self.assertEqual(response.status_code, 400)

    def test_pagination_reduces_item_count(self):
        response = self.client.get(self.url, {'page': 2, 'limit': 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['page'], 2)
        self.assertEqual(payload['limit'], 1)
        self.assertEqual(payload['total'], 3)
        self.assertTrue(payload['has_next'])
        self.assertEqual(len(payload['items']), 1)


class ErpApontamentosMontagemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='apontador', password='senha')
        cls.setor = Setor.objects.create(nome='montagem')
        cls.maquina = Maquina.objects.create(nome='Celula A', setor=cls.setor, tipo='maquina')
        cls.operador = Operador.objects.create(matricula='001', nome='Operador', setor=cls.setor)

        cls.ordem_montagem = Ordem.objects.create(
            ordem=9001,
            grupo_maquina='montagem',
            maquina=cls.maquina,
            status_atual='finalizada',
        )
        cls.item_montagem = PecasOrdem.objects.create(
            ordem=cls.ordem_montagem,
            peca='030341 - Conjunto Montagem',
            qtd_planejada=10,
            qtd_boa=7,
            qtd_morta=0,
        )

        ordem_sem_producao = Ordem.objects.create(
            ordem=9002,
            grupo_maquina='montagem',
            maquina=cls.maquina,
            status_atual='finalizada',
        )
        PecasOrdem.objects.create(
            ordem=ordem_sem_producao,
            peca='030342 - Sem producao',
            qtd_planejada=10,
            qtd_boa=0,
        )

        ordem_outro_setor = Ordem.objects.create(
            ordem=9003,
            grupo_maquina='estamparia',
            maquina=cls.maquina,
            status_atual='finalizada',
        )
        PecasOrdem.objects.create(
            ordem=ordem_outro_setor,
            peca='030343 - Outro setor',
            qtd_planejada=10,
            qtd_boa=5,
        )

        cls.list_url = reverse('montagem:api_erp_apontamentos_montagem')

    def setUp(self):
        self.client.force_login(self.user)

    def test_listagem_retorna_apenas_montagem_com_qtd_boa(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['pagination']['total_items'], 1)
        self.assertEqual(payload['results'][0]['ordem'], self.ordem_montagem.ordem)
        self.assertEqual(payload['results'][0]['peca_codigo'], '030341')
        self.assertEqual(payload['results'][0]['peca_descricao'], 'Conjunto Montagem')

    def test_filtros_principais(self):
        response_ordem = self.client.get(self.list_url, {'ordem': '9001'})
        response_peca = self.client.get(self.list_url, {'peca': 'Conjunto'})
        response_apontado = self.client.get(self.list_url, {'apontado': 'false'})

        self.assertEqual(response_ordem.status_code, 200)
        self.assertEqual(response_ordem.json()['pagination']['total_items'], 1)
        self.assertEqual(response_peca.status_code, 200)
        self.assertEqual(response_peca.json()['pagination']['total_items'], 1)
        self.assertEqual(response_apontado.status_code, 200)
        self.assertEqual(response_apontado.json()['pagination']['total_items'], 1)

    def test_apontamento_manual_marca_item_e_gera_chave(self):
        url = reverse('montagem:api_erp_apontar_item_montagem', args=[self.item_montagem.id])

        response = self.client.post(
            url,
            data={'tipo_apontamento': 'manual'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.item_montagem.refresh_from_db()
        self.assertTrue(self.item_montagem.apontado)
        self.assertEqual(self.item_montagem.tipo_apontamento, 'manual')
        self.assertEqual(self.item_montagem.chave_apontamento, f'MANUAL-MONTAGEM-ITEM-{self.item_montagem.id}')
        self.assertEqual(self.item_montagem.resp_apontamento, self.user)

    def test_apontamento_duplicado_na_mesma_ordem_retorna_409(self):
        self.item_montagem.apontado = True
        self.item_montagem.tipo_apontamento = 'manual'
        self.item_montagem.chave_apontamento = f'MANUAL-MONTAGEM-ITEM-{self.item_montagem.id}'
        self.item_montagem.data_apontamento = now()
        self.item_montagem.resp_apontamento = self.user
        self.item_montagem.save()

        segundo_item = PecasOrdem.objects.create(
            ordem=self.ordem_montagem,
            peca='030344 - Segundo item',
            qtd_planejada=5,
            qtd_boa=2,
        )
        url = reverse('montagem:api_erp_apontar_item_montagem', args=[segundo_item.id])

        response = self.client.post(
            url,
            data={'tipo_apontamento': 'manual'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['already_apontado'])

    @patch('apontamento_montagem.views.requests.post')
    def test_payload_api_usa_processo_montagem_e_codigo_extraido(self, mock_post):
        class MockResponse:
            ok = True
            status_code = 200
            text = ''

            def json(self):
                return {'status': 'success', 'chave': 'CHAVE-123'}

        mock_post.return_value = MockResponse()
        url = reverse('montagem:api_erp_apontar_item_montagem', args=[self.item_montagem.id])

        response = self.client.post(
            url,
            data={'tipo_apontamento': 'api'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload_enviado = mock_post.call_args.kwargs['json']
        self.assertEqual(payload_enviado['processo'], 'S Mont Conjuntos Carretas')
        self.assertEqual(payload_enviado['recurso'], '030341')
        self.assertEqual(payload_enviado['id'], f'montagem-item-{self.item_montagem.id}')

        self.item_montagem.refresh_from_db()
        self.assertTrue(self.item_montagem.apontado)
        self.assertEqual(self.item_montagem.chave_apontamento, 'CHAVE-123')

    def test_api_com_qtd_morta_retorna_422_e_salva_erro(self):
        item = PecasOrdem.objects.create(
            ordem=self.ordem_montagem,
            peca='030345 - Item com morta',
            qtd_planejada=5,
            qtd_boa=2,
            qtd_morta=1,
        )
        url = reverse('montagem:api_erp_apontar_item_montagem', args=[item.id])

        response = self.client.post(
            url,
            data={'tipo_apontamento': 'api'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 422)
        item.refresh_from_db()
        self.assertFalse(item.apontado)
        self.assertEqual(item.tipo_apontamento, 'api')
        self.assertIn('qtd_morta', item.erro_apontamento)

    @patch('apontamento_montagem.views.requests.post')
    def test_finalizar_ordem_na_tela_montagem_aponta_erp_e_retorna_chave(self, mock_post):
        class MockResponse:
            ok = True
            status_code = 200
            text = ''

            def json(self):
                return {'status': 'success', 'chave': 'CHAVE-MONTAGEM-1'}

        mock_post.return_value = MockResponse()
        ordem = Ordem.objects.create(
            ordem=9010,
            grupo_maquina='montagem',
            maquina=self.maquina,
            status_atual='iniciada',
        )
        processo = OrdemProcesso.objects.create(
            ordem=ordem,
            status='iniciada',
            data_inicio=now(),
        )
        item = PecasOrdem.objects.create(
            ordem=ordem,
            peca='030999 - Conjunto Finalizacao',
            qtd_planejada=3,
            qtd_boa=0,
            processo_ordem=processo,
        )
        url = reverse('montagem:atualizar_status_ordem')

        response = self.client.post(
            url,
            data={
                'status': 'finalizada',
                'ordem_id': ordem.id,
                'operador_final': self.operador.id,
                'obs_finalizar': 'ok',
                'qt_realizada': 3,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['chave_apontamento'], 'CHAVE-MONTAGEM-1')
        self.assertEqual(payload['apontamento_erp']['chave_apontamento'], 'CHAVE-MONTAGEM-1')

        item.refresh_from_db()
        self.assertTrue(item.apontado)
        self.assertEqual(item.tipo_apontamento, 'api')
        self.assertEqual(item.chave_apontamento, 'CHAVE-MONTAGEM-1')

        payload_enviado = mock_post.call_args.kwargs['json']
        self.assertEqual(payload_enviado['processo'], 'S Mont Conjuntos Carretas')
        self.assertEqual(payload_enviado['recurso'], '030999')
