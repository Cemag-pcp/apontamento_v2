from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from apontamento_montagem.models import PecasOrdem
from cadastro.models import Maquina, Setor
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
