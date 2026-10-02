from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cadastro_almox.models import DepositoDestino, Funcionario, ItensTransferencia, OperadorAlmox
from core.models import Profile
from core_almox.views import CHAVE_CONFIRMADA_MANUAL, CHAVE_VERIFICAR
from solicitacao_almox.models import SolicitacaoTransferencia


def _resposta_innovaro(json_data, status=200):
    resposta = MagicMock()
    resposta.ok = 200 <= status < 300
    resposta.status_code = status
    resposta.json.return_value = json_data
    resposta.text = str(json_data)
    return resposta


class FilaVerificacaoTransferenciaTests(TestCase):
    """Transferencia sem resposta do Innovaro (read timeout) nao pode ser
    liberada pra reenvio automatico: vai pra fila de verificacao manual."""

    def setUp(self):
        self.user = User.objects.create_user(username="almox_teste", password="123456")
        Profile.objects.create(user=self.user, tipo_acesso="admin")
        self.client.force_login(self.user)

        self.operador = OperadorAlmox.objects.create(matricula="12345", nome="Operador Teste")
        funcionario = Funcionario.objects.create(nome="Solicitante", matricula="999999")
        deposito = DepositoDestino.objects.create(nome="Almox Pintura - Embalagem")
        item = ItensTransferencia.objects.create(codigo="313210", nome="Tinta")
        self.sol = SolicitacaoTransferencia.objects.create(
            funcionario=funcionario, deposito_destino=deposito, item=item, quantidade=2,
        )
        self.url = reverse("lista_solicitacoes")

    def _entregar(self):
        return self.client.post(self.url, {
            "entregar": "1", "solicitacao_id": self.sol.id, "tipo_solicitacao": "transferencia",
            "matricula": self.operador.matricula, "data_entrega": "2026-10-02T10:00",
        })

    def _verificacao(self, acao, chave=""):
        return self.client.post(self.url, {
            acao: "1", "solicitacao_id": self.sol.id,
            "matricula": self.operador.matricula, "data_entrega": "2026-10-02T10:00",
            "chave_innovaro": chave,
        })

    @patch("core_almox.views.requests.post", side_effect=requests.exceptions.ReadTimeout("Read timed out"))
    def test_read_timeout_vai_para_fila_e_bloqueia_reenvio(self, post):
        resposta = self._entregar()
        self.assertEqual(resposta.status_code, 502)
        self.assertIn("verificação manual", resposta.json()["mensagem"])

        self.sol.refresh_from_db()
        self.assertEqual(self.sol.chave_innovaro, CHAVE_VERIFICAR)
        self.assertIsNone(self.sol.entregue_por)
        self.assertIn("VERIFICAR NO INNOVARO", self.sol.rpa)

        # clicar Entregar de novo NAO chama o Innovaro (evita a duplicidade)
        resposta = self._entregar()
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(post.call_count, 1)

    @patch("core_almox.views.requests.post", side_effect=requests.exceptions.ConnectionError("sem rede"))
    def test_falha_de_conexao_continua_liberando(self, post):
        self._entregar()
        self.sol.refresh_from_db()
        self.assertIsNone(self.sol.chave_innovaro)
        self.assertIsNone(self.sol.entregue_por)

    @patch("core_almox.views.requests.post", side_effect=requests.exceptions.ReadTimeout("Read timed out"))
    def test_confirmar_que_ja_esta_no_innovaro(self, post):
        self._entregar()
        resposta = self._verificacao("verificacao_confirmar", chave="102498868")

        self.assertEqual(resposta.status_code, 200)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.entregue_por, self.operador)
        self.assertEqual(self.sol.chave_innovaro, "102498868")
        self.assertIn("CONFIRMADA MANUALMENTE", self.sol.rpa)
        self.assertEqual(post.call_count, 1)  # nao reenviou

    @patch("core_almox.views.requests.post", side_effect=requests.exceptions.ReadTimeout("Read timed out"))
    def test_confirmar_sem_chave(self, post):
        self._entregar()
        self._verificacao("verificacao_confirmar")
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.chave_innovaro, CHAVE_CONFIRMADA_MANUAL)

    def test_transferir_de_novo(self):
        with patch("core_almox.views.requests.post", side_effect=requests.exceptions.ReadTimeout("x")):
            self._entregar()

        sucesso = _resposta_innovaro({"status": "Success", "chaveTransferencia": 555})
        with patch("core_almox.views.requests.post", return_value=sucesso) as post:
            resposta = self._verificacao("verificacao_reenviar")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(post.call_count, 1)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.chave_innovaro, "555")
        self.assertEqual(self.sol.entregue_por, self.operador)

    def test_resolver_duas_vezes_e_recusado(self):
        with patch("core_almox.views.requests.post", side_effect=requests.exceptions.ReadTimeout("x")):
            self._entregar()
        self._verificacao("verificacao_confirmar")
        resposta = self._verificacao("verificacao_reenviar")
        self.assertEqual(resposta.status_code, 409)

    def test_lote_com_item_ausente_na_resposta_vai_para_fila(self):
        resposta_lote = _resposta_innovaro([])  # Innovaro nao devolveu o item
        with patch("core_almox.views.requests.post", return_value=resposta_lote):
            resposta = self.client.post(self.url, {
                "entregar_lote": "1", "solicitacao_ids[]": [self.sol.id],
                "matricula": self.operador.matricula, "data_entrega": "2026-10-02T10:00",
            })
        self.assertEqual(resposta.json()["verificar"], [self.sol.id])
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.chave_innovaro, CHAVE_VERIFICAR)
        self.assertIsNone(self.sol.entregue_por)

    @patch("core_almox.views.busca_saldo_recurso_central", return_value=({}, ""))
    def test_listagem_separa_a_fila(self, _saldo):
        with patch("core_almox.views.requests.post", side_effect=requests.exceptions.ReadTimeout("x")):
            self._entregar()
        dados = self.client.post(self.url, {"type_sol": "transferencia"}).json()
        self.assertEqual([t["id"] for t in dados["verificacao_manual"]], [self.sol.id])
        self.assertEqual(dados["transferencias"], [])
