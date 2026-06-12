import json
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastro.models import Maquina, Setor
from core.models import Ordem, OrdemProcesso, Profile, RotaAcesso

from .models import Report


class ReportConclusaoTests(TestCase):
    def setUp(self):
        self.pcp = User.objects.create_user(username='pcp', password='senha')
        Profile.objects.create(user=self.pcp, tipo_acesso='pcp')

        self.admin = User.objects.create_user(username='admin', password='senha')
        Profile.objects.create(user=self.admin, tipo_acesso='admin')

        self.operador = User.objects.create_user(username='operador', password='senha')
        Profile.objects.create(user=self.operador, tipo_acesso='operador')
        self.setor = Setor.objects.create(nome='setor_conclusao')

        self.report = Report.objects.create(
            usuario=self.operador,
            texto='Report de teste',
            data=date.today(),
            setor=self.setor,
        )
        self.url = reverse(
            'reuniao:atualizar_conclusao_report',
            args=[self.report.id],
        )

    def post_conclusao(self, concluido):
        return self.client.post(
            self.url,
            data=json.dumps({'concluido': concluido}),
            content_type='application/json',
        )

    def test_report_existente_inicia_nao_concluido(self):
        self.assertFalse(self.report.concluido)

    def test_pcp_pode_marcar_e_desmarcar(self):
        self.client.force_login(self.pcp)

        response = self.post_conclusao(True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'id': self.report.id, 'concluido': True})
        self.report.refresh_from_db()
        self.assertTrue(self.report.concluido)

        response = self.post_conclusao(False)
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertFalse(self.report.concluido)

    def test_admin_pode_marcar_e_desmarcar(self):
        self.client.force_login(self.admin)

        response = self.post_conclusao(True)
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertTrue(self.report.concluido)

        response = self.post_conclusao(False)
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertFalse(self.report.concluido)

    def test_usuario_nao_pcp_recebe_403(self):
        self.client.force_login(self.operador)

        response = self.post_conclusao(True)

        self.assertEqual(response.status_code, 403)
        self.report.refresh_from_db()
        self.assertFalse(self.report.concluido)

    def test_usuario_nao_autenticado_e_redirecionado(self):
        response = self.post_conclusao(True)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/core/login/', response.url)

    def test_report_inexistente_retorna_404(self):
        self.client.force_login(self.pcp)
        url = reverse('reuniao:atualizar_conclusao_report', args=[999999])

        response = self.client.post(
            url,
            data=json.dumps({'concluido': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)

    def test_listagem_inclui_estado_concluido(self):
        self.report.concluido = True
        self.report.save(update_fields=['concluido'])
        self.client.force_login(self.operador)

        response = self.client.get(
            reverse('reuniao:listar_reports'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['reports'][0]['concluido'])

    def test_listagem_retorna_reports_atuais_e_historicos(self):
        historico = Report.objects.create(
            usuario=self.operador,
            texto='Report histórico',
            data=date(2026, 1, 10),
            setor=self.setor,
        )
        self.client.force_login(self.operador)

        response = self.client.get(reverse('reuniao:listar_reports'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['total_items'], 2)
        self.assertEqual(
            {item['id'] for item in payload['reports']},
            {self.report.id, historico.id},
        )

    def test_payload_exige_booleano(self):
        self.client.force_login(self.pcp)

        response = self.client.post(
            self.url,
            data=json.dumps({'concluido': 'sim'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.report.refresh_from_db()
        self.assertFalse(self.report.concluido)

    def test_tela_habilita_controle_para_pcp(self):
        self.client.force_login(self.pcp)

        response = self.client.get(reverse('reuniao:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'const PODE_CONCLUIR_REPORTS = true;')
        self.assertContains(response, 'const PODE_EXCLUIR_REPORTS = true;')
        self.assertContains(
            response,
            'Atenção: esta ação não poderá ser desfeita.',
        )

    def test_tela_habilita_controles_para_admin(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('reuniao:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'const PODE_CONCLUIR_REPORTS = true;')
        self.assertContains(response, 'const PODE_EXCLUIR_REPORTS = true;')

    def test_tela_deixa_controle_somente_leitura_para_nao_pcp(self):
        rota_reuniao = RotaAcesso.objects.get(nome='reuniao')
        self.operador.profile.permissoes.add(rota_reuniao)
        self.client.force_login(self.operador)

        response = self.client.get(reverse('reuniao:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'const PODE_CONCLUIR_REPORTS = false;')
        self.assertContains(response, 'const PODE_EXCLUIR_REPORTS = false;')


class ReportExclusaoTests(TestCase):
    def setUp(self):
        self.pcp = User.objects.create_user(username='pcp-exclusao', password='senha')
        Profile.objects.create(user=self.pcp, tipo_acesso='pcp')

        self.admin = User.objects.create_user(username='admin-exclusao', password='senha')
        Profile.objects.create(user=self.admin, tipo_acesso='admin')

        self.operador = User.objects.create_user(
            username='operador-exclusao',
            password='senha',
        )
        Profile.objects.create(user=self.operador, tipo_acesso='operador')

        self.report = Report.objects.create(
            usuario=self.operador,
            texto='Report que será excluído',
            data=date(2026, 1, 10),
        )
        self.url = reverse('reuniao:excluir_report', args=[self.report.id])

    def test_pcp_exclui_report_historico_definitivamente(self):
        self.client.force_login(self.pcp)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {'id': self.report.id, 'excluido': True},
        )
        self.assertFalse(Report.objects.filter(pk=self.report.id).exists())

    def test_admin_exclui_report_definitivamente(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Report.objects.filter(pk=self.report.id).exists())

    def test_usuario_nao_pcp_recebe_403_e_report_permanece(self):
        self.client.force_login(self.operador)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Report.objects.filter(pk=self.report.id).exists())

    def test_usuario_nao_autenticado_e_redirecionado(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/core/login/', response.url)
        self.assertTrue(Report.objects.filter(pk=self.report.id).exists())

    def test_report_inexistente_retorna_404(self):
        self.client.force_login(self.pcp)
        url = reverse('reuniao:excluir_report', args=[999999])

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)


class ReportSetorTests(TestCase):
    def setUp(self):
        self.setor_corte = Setor.objects.create(nome='setor_teste_corte')
        self.setor_solda = Setor.objects.create(nome='setor_teste_solda')
        self.setor_pintura = Setor.objects.create(nome='setor_teste_pintura')

        self.usuario = User.objects.create_user(
            username='usuario-setores',
            password='senha',
        )
        self.profile = Profile.objects.create(
            user=self.usuario,
            tipo_acesso='operador',
        )
        self.client.force_login(self.usuario)
        self.criar_url = reverse('reuniao:criar_report')
        self.listar_url = reverse('reuniao:listar_reports')

    def criar_report(self, texto='Report por setor', setor_id=None):
        payload = {'texto': texto}
        if setor_id is not None:
            payload['setor_id'] = setor_id
        return self.client.post(
            self.criar_url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_usuario_pode_ter_zero_um_ou_varios_setores(self):
        self.assertEqual(self.profile.setores.count(), 0)

        self.profile.setores.add(self.setor_corte)
        self.assertEqual(list(self.profile.setores.all()), [self.setor_corte])

        self.profile.setores.add(self.setor_solda)
        self.assertEqual(self.profile.setores.count(), 2)

    def test_usuario_sem_setor_nao_pode_criar_report(self):
        response = self.criar_report()

        self.assertEqual(response.status_code, 400)
        self.assertIn('não possui setor vinculado', response.json()['error'])
        self.assertFalse(Report.objects.filter(usuario=self.usuario).exists())

    def test_usuario_com_um_setor_cria_report_no_setor_selecionado(self):
        self.profile.setores.add(self.setor_corte)

        response = self.criar_report(setor_id=self.setor_corte.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['setor']['id'], self.setor_corte.id)

    def test_usuario_com_setores_precisa_selecionar_um(self):
        self.profile.setores.add(self.setor_corte, self.setor_solda)

        response = self.criar_report()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Report.objects.filter(usuario=self.usuario).exists())

    def test_usuario_nao_pode_usar_setor_nao_vinculado(self):
        self.profile.setores.add(self.setor_corte)

        response = self.criar_report(setor_id=self.setor_solda.id)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Report.objects.filter(usuario=self.usuario).exists())

    def test_setor_historico_nao_muda_com_perfil(self):
        self.profile.setores.add(self.setor_corte)
        response = self.criar_report(setor_id=self.setor_corte.id)
        report = Report.objects.get(pk=response.json()['id'])

        self.profile.setores.set([self.setor_solda])
        report.refresh_from_db()

        self.assertEqual(report.setor, self.setor_corte)

    def test_filtros_todos_setor_e_confirmacao(self):
        report_corte = Report.objects.create(
            usuario=self.usuario,
            texto='Corte',
            data=date.today(),
            setor=self.setor_corte,
            concluido=True,
        )
        report_solda = Report.objects.create(
            usuario=self.usuario,
            texto='Solda',
            data=date.today(),
            setor=self.setor_solda,
        )
        Report.objects.create(
            usuario=self.usuario,
            texto='Sem setor',
            data=date.today(),
        )
        Report.objects.create(
            usuario=self.usuario,
            texto='Histórico',
            data=date(2026, 1, 10),
            setor=self.setor_corte,
        )

        todos = self.client.get(self.listar_url).json()['reports']
        corte = self.client.get(
            self.listar_url,
            {'setor': self.setor_corte.id},
        ).json()['reports']
        confirmados = self.client.get(
            self.listar_url,
            {'concluido': 'true'},
        ).json()['reports']
        nao_confirmados_solda = self.client.get(
            self.listar_url,
            {'setor': self.setor_solda.id, 'concluido': 'false'},
        ).json()['reports']

        self.assertEqual(
            {item['id'] for item in todos},
            {
                report_corte.id,
                report_solda.id,
                Report.objects.get(texto='Histórico').id,
            },
        )
        self.assertEqual(
            {item['id'] for item in corte},
            {report_corte.id, Report.objects.get(texto='Histórico').id},
        )
        self.assertEqual([item['id'] for item in confirmados], [report_corte.id])
        self.assertEqual(
            [item['id'] for item in nao_confirmados_solda],
            [report_solda.id],
        )

    def test_paginacao_retorna_seis_reports_por_pagina(self):
        reports = [
            Report.objects.create(
                usuario=self.usuario,
                texto=f'Report paginado {indice}',
                data=date(2026, 1, indice + 1),
                setor=self.setor_corte,
            )
            for indice in range(7)
        ]

        pagina_1 = self.client.get(self.listar_url, {'page': 1}).json()
        pagina_2 = self.client.get(self.listar_url, {'page': 2}).json()

        self.assertEqual(len(pagina_1['reports']), 6)
        self.assertEqual(len(pagina_2['reports']), 1)
        self.assertEqual(pagina_1['page'], 1)
        self.assertEqual(pagina_1['total_pages'], 2)
        self.assertEqual(pagina_1['total_items'], 7)
        self.assertFalse(pagina_1['has_previous'])
        self.assertTrue(pagina_1['has_next'])
        self.assertTrue(pagina_2['has_previous'])
        self.assertFalse(pagina_2['has_next'])
        self.assertEqual(pagina_1['reports'][0]['id'], reports[-1].id)

    def test_pagina_alem_do_fim_retorna_ultima_pagina(self):
        Report.objects.create(
            usuario=self.usuario,
            texto='Único report',
            data=date.today(),
            setor=self.setor_corte,
        )

        response = self.client.get(self.listar_url, {'page': 99})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['page'], 1)

    def test_filtros_sao_aplicados_antes_da_paginacao(self):
        for indice in range(7):
            Report.objects.create(
                usuario=self.usuario,
                texto=f'Corte confirmado {indice}',
                data=date(2025, 12, indice + 1),
                setor=self.setor_corte,
                concluido=True,
            )
        Report.objects.create(
            usuario=self.usuario,
            texto='Solda confirmada',
            data=date.today(),
            setor=self.setor_solda,
            concluido=True,
        )

        pagina_1 = self.client.get(self.listar_url, {
            'setor': self.setor_corte.id,
            'concluido': 'true',
            'page': 1,
        }).json()
        pagina_2 = self.client.get(self.listar_url, {
            'setor': self.setor_corte.id,
            'concluido': 'true',
            'page': 2,
        }).json()

        self.assertEqual(pagina_1['total_items'], 7)
        self.assertEqual(pagina_1['total_pages'], 2)
        self.assertEqual(len(pagina_1['reports']), 6)
        self.assertEqual(len(pagina_2['reports']), 1)
        self.assertTrue(all(
            item['setor']['id'] == self.setor_corte.id
            and item['concluido']
            for item in pagina_1['reports'] + pagina_2['reports']
        ))

    def test_filtro_por_data_retorna_somente_o_dia_selecionado(self):
        data_selecionada = date(2026, 2, 10)
        report_do_dia = Report.objects.create(
            usuario=self.usuario,
            texto='Report da data',
            data=data_selecionada,
            setor=self.setor_corte,
        )
        Report.objects.create(
            usuario=self.usuario,
            texto='Report de outra data',
            data=date(2026, 2, 11),
            setor=self.setor_corte,
        )

        response = self.client.get(
            self.listar_url,
            {'data': data_selecionada.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_items'], 1)
        self.assertEqual(
            [item['id'] for item in response.json()['reports']],
            [report_do_dia.id],
        )

    def test_filtro_de_data_combina_setor_status_e_paginacao(self):
        data_selecionada = date(2026, 3, 15)
        reports_esperados = [
            Report.objects.create(
                usuario=self.usuario,
                texto=f'Corte confirmado na data {indice}',
                data=data_selecionada,
                setor=self.setor_corte,
                concluido=True,
            )
            for indice in range(7)
        ]
        Report.objects.create(
            usuario=self.usuario,
            texto='Corte não confirmado na data',
            data=data_selecionada,
            setor=self.setor_corte,
        )
        Report.objects.create(
            usuario=self.usuario,
            texto='Solda confirmada na data',
            data=data_selecionada,
            setor=self.setor_solda,
            concluido=True,
        )

        pagina_1 = self.client.get(self.listar_url, {
            'data': data_selecionada.isoformat(),
            'setor': self.setor_corte.id,
            'concluido': 'true',
            'page': 1,
        }).json()
        pagina_2 = self.client.get(self.listar_url, {
            'data': data_selecionada.isoformat(),
            'setor': self.setor_corte.id,
            'concluido': 'true',
            'page': 2,
        }).json()

        retornados = pagina_1['reports'] + pagina_2['reports']
        self.assertEqual(pagina_1['total_items'], 7)
        self.assertEqual(pagina_1['total_pages'], 2)
        self.assertEqual(
            {item['id'] for item in retornados},
            {report.id for report in reports_esperados},
        )

    def test_filtro_de_data_invalido_retorna_400(self):
        response = self.client.get(
            self.listar_url,
            {'data': '15-03-2026'},
        )

        self.assertEqual(response.status_code, 400)

    def test_filtro_de_confirmacao_invalido_retorna_400(self):
        response = self.client.get(
            self.listar_url,
            {'concluido': 'talvez'},
        )

        self.assertEqual(response.status_code, 400)

    def test_template_exibe_filtros_sem_opcao_sem_setor(self):
        rota_reuniao = RotaAcesso.objects.get(nome='reuniao')
        self.profile.permissoes.add(rota_reuniao)
        response = self.client.get(reverse('reuniao:home'))

        self.assertContains(response, 'id="reports-setor-filtro"')
        self.assertContains(response, 'id="reports-conclusao-filtro"')
        self.assertContains(response, 'id="reports-data-filtro"')
        self.assertContains(response, 'Confirmados')
        self.assertContains(response, 'Não confirmados')
        self.assertContains(response, '> Reports</span>', html=False)
        self.assertContains(response, 'id="reports-paginacao"')
        self.assertContains(response, 'Nenhum report encontrado.')
        self.assertNotContains(response, 'Reports do Dia')
        self.assertNotContains(response, 'Nenhum report hoje.')
        self.assertNotContains(response, '<option value="sem-setor">')

    def test_admin_pode_reportar_para_setor_nao_vinculado(self):
        admin = User.objects.create_user(username='admin-report-setor', password='senha')
        Profile.objects.create(user=admin, tipo_acesso='admin')
        self.client.force_login(admin)

        response = self.criar_report(setor_id=self.setor_pintura.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['setor']['id'], self.setor_pintura.id)

    def test_admin_precisa_escolher_setor(self):
        admin = User.objects.create_user(
            username='admin-report-sem-setor',
            password='senha',
        )
        Profile.objects.create(user=admin, tipo_acesso='admin')
        self.client.force_login(admin)

        response = self.criar_report()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Report.objects.filter(usuario=admin).exists())

    def test_pcp_pode_reportar_para_qualquer_setor(self):
        pcp = User.objects.create_user(username='pcp-report-setor', password='senha')
        Profile.objects.create(user=pcp, tipo_acesso='pcp')
        self.client.force_login(pcp)

        response = self.criar_report(setor_id=self.setor_solda.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['setor']['id'], self.setor_solda.id)


class AndamentoLivePeriodoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin-periodo-live',
            password='senha',
        )
        Profile.objects.create(user=self.admin, tipo_acesso='admin')
        self.client.force_login(self.admin)
        self.url = reverse('reuniao:andamento_live')
        self.setor = Setor.objects.create(nome='setor_periodo_live')
        self.maquina = Maquina.objects.create(
            nome='Máquina período',
            setor=self.setor,
            tipo='maquina',
        )
        self.data_inicio = date(2026, 6, 1)
        self.data_fim = date(2026, 6, 5)

    def criar_ordem(self, status, inicio, excluida=False, grupo='estamparia'):
        ordem = Ordem.objects.create(
            grupo_maquina=grupo,
            maquina=self.maquina,
            status_atual=status,
            excluida=excluida,
        )
        OrdemProcesso.objects.create(
            ordem=ordem,
            status='iniciada',
            data_inicio=timezone.make_aware(datetime.combine(inicio, time(10, 0))),
        )
        return ordem

    def consultar(self, setor='estamparia', data_inicio=None, data_fim=None):
        return self.client.get(self.url, {
            'setor': setor,
            'data_inicio': (data_inicio or self.data_inicio).isoformat(),
            'data_fim': (data_fim or self.data_fim).isoformat(),
        })

    def test_quatro_setores_aceitam_periodo(self):
        for setor in ('estamparia', 'usinagem', 'serra', 'corte'):
            with self.subTest(setor=setor):
                response = self.consultar(setor=setor)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['data_inicio'], '2026-06-01')
                self.assertEqual(response.json()['data_fim'], '2026-06-05')

    def test_periodo_inclusivo_retorna_finalizadas_e_interrompidas(self):
        inicio = self.criar_ordem('finalizada', self.data_inicio)
        fim = self.criar_ordem('interrompida', self.data_fim)
        fora = self.criar_ordem('iniciada', self.data_inicio - timedelta(days=1))
        excluida = self.criar_ordem('finalizada', self.data_inicio, excluida=True)

        response = self.consultar()

        self.assertEqual(response.status_code, 200)
        ordens = response.json()['ordens']
        numeros = {item['ordem'] for item in ordens}
        self.assertEqual(numeros, {inicio.ordem, fim.ordem})
        self.assertNotIn(fora.ordem, numeros)
        self.assertNotIn(excluida.ordem, numeros)
        self.assertEqual(
            {item['status'] for item in ordens},
            {'Finalizada', 'Interrompida'},
        )

    def test_usa_inicio_mais_recente_da_producao(self):
        ordem = self.criar_ordem('finalizada', self.data_inicio)
        OrdemProcesso.objects.create(
            ordem=ordem,
            status='iniciada',
            data_inicio=timezone.make_aware(datetime.combine(
                self.data_fim + timedelta(days=1),
                time(8, 0),
            )),
        )

        response = self.consultar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ordens'], [])

    def test_rejeita_setor_datas_e_intervalo_invalidos(self):
        setor_invalido = self.consultar(setor='montagem')
        data_invalida = self.client.get(self.url, {
            'setor': 'estamparia',
            'data_inicio': 'invalida',
            'data_fim': '2026-06-05',
        })
        intervalo_invertido = self.consultar(
            data_inicio=self.data_fim,
            data_fim=self.data_inicio,
        )

        self.assertEqual(setor_invalido.status_code, 400)
        self.assertEqual(data_invalida.status_code, 400)
        self.assertEqual(intervalo_invertido.status_code, 400)

    def test_template_exibe_e_envia_periodo_live(self):
        response = self.client.get(reverse('reuniao:home'))

        self.assertContains(response, 'id="periodo-live-container"')
        self.assertContains(response, 'id="live-data-inicio"')
        self.assertContains(response, 'id="live-data-fim"')
        self.assertContains(response, 'data_inicio: cfg.liveDataInicio')
        self.assertContains(response, 'data_fim: cfg.liveDataFim')
        self.assertContains(response, 'liveDataInicio: getTodayStr()')
        self.assertContains(response, 'liveDataFim: getTodayStr()')
        self.assertContains(response, "datasContainer.classList.toggle('d-none', live)")
        self.assertContains(response, "datasContainer.classList.toggle('d-flex', !live)")


class UsuarioSetorApiTests(TestCase):
    def setUp(self):
        self.setor_corte = Setor.objects.create(nome='api_setor_corte')
        self.setor_solda = Setor.objects.create(nome='api_setor_solda')
        self.admin = User.objects.create_user(username='admin-setores', password='senha')
        Profile.objects.create(user=self.admin, tipo_acesso='admin')
        self.client.force_login(self.admin)

    def test_criar_usuario_com_varios_setores(self):
        response = self.client.post(
            reverse('core:criar_usuario'),
            data=json.dumps({
                'username': 'novo-usuario-setores',
                'password': 'senha',
                'tipo_acesso': 'operador',
                'setor_ids': [self.setor_corte.id, self.setor_solda.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        profile = Profile.objects.get(user__username='novo-usuario-setores')
        self.assertEqual(
            set(profile.setores.values_list('id', flat=True)),
            {self.setor_corte.id, self.setor_solda.id},
        )

    def test_criar_usuario_rejeita_setor_invalido(self):
        response = self.client.post(
            reverse('core:criar_usuario'),
            data=json.dumps({
                'username': 'usuario-setor-invalido',
                'password': 'senha',
                'tipo_acesso': 'operador',
                'setor_ids': [999999],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='usuario-setor-invalido').exists())

    def test_atualizar_permissoes_nao_altera_setores(self):
        usuario = User.objects.create_user(username='editar-setores', password='senha')
        profile = Profile.objects.create(user=usuario, tipo_acesso='operador')
        profile.setores.add(self.setor_corte)

        response = self.client.post(
            reverse('core:atualizar_acessos', args=[usuario.id]),
            data=json.dumps({
                'permissoes': [],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(profile.setores.all()), [self.setor_corte])

    def test_listagem_de_usuarios_inclui_setores(self):
        usuario = User.objects.create_user(username='listar-setores', password='senha')
        profile = Profile.objects.create(user=usuario, tipo_acesso='operador')
        profile.setores.add(self.setor_corte)

        response = self.client.get(reverse('core:listar_usuarios'))

        self.assertEqual(response.status_code, 200)
        usuario_json = next(
            item for item in response.json()
            if item['id'] == usuario.id
        )
        self.assertEqual(
            usuario_json['setores'],
            [{'id': self.setor_corte.id, 'nome': self.setor_corte.nome}],
        )

    def test_nao_admin_nao_pode_editar_setores(self):
        operador = User.objects.create_user(username='sem-admin-setores', password='senha')
        Profile.objects.create(user=operador, tipo_acesso='operador')
        alvo = User.objects.create_user(username='alvo-setores', password='senha')
        Profile.objects.create(user=alvo, tipo_acesso='operador')
        self.client.force_login(operador)

        response = self.client.post(
            reverse('core:atualizar_acessos', args=[alvo.id]),
            data=json.dumps({
                'permissoes': [],
                'setor_ids': [self.setor_corte.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(alvo.profile.setores.exists())


class UsuarioEdicaoApiTests(TestCase):
    def setUp(self):
        self.setor_corte = Setor.objects.create(nome='edicao_setor_corte')
        self.setor_solda = Setor.objects.create(nome='edicao_setor_solda')
        self.admin = User.objects.create_user(
            username='admin-edicao',
            password='senha-atual',
        )
        Profile.objects.create(user=self.admin, tipo_acesso='admin')
        self.usuario = User.objects.create_user(
            username='usuario-edicao',
            password='senha-original',
        )
        self.profile = Profile.objects.create(
            user=self.usuario,
            tipo_acesso='operador',
        )
        self.client.force_login(self.admin)
        self.url = reverse('core:editar_usuario', args=[self.usuario.id])

    def editar(self, username='usuario-editado', password='', setor_ids=None):
        return self.client.post(
            self.url,
            data=json.dumps({
                'username': username,
                'password': password,
                'setor_ids': setor_ids if setor_ids is not None else [],
            }),
            content_type='application/json',
        )

    def test_apenas_admin_pode_editar(self):
        operador = User.objects.create_user(username='operador-sem-edicao', password='senha')
        Profile.objects.create(user=operador, tipo_acesso='operador')
        self.client.force_login(operador)

        response = self.editar()

        self.assertEqual(response.status_code, 403)

    def test_usuario_nao_autenticado_e_redirecionado(self):
        self.client.logout()

        response = self.editar()

        self.assertEqual(response.status_code, 302)

    def test_usuario_inexistente_retorna_404(self):
        self.url = reverse('core:editar_usuario', args=[999999])

        response = self.editar()

        self.assertEqual(response.status_code, 404)

    def test_nome_vazio_nao_altera_usuario(self):
        response = self.editar(username='   ')

        self.assertEqual(response.status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'usuario-edicao')

    def test_nome_duplicado_nao_altera_usuario_ou_setores(self):
        User.objects.create_user(username='nome-existente', password='senha')

        response = self.editar(
            username='nome-existente',
            setor_ids=[self.setor_corte.id],
        )

        self.assertEqual(response.status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'usuario-edicao')
        self.assertFalse(self.profile.setores.exists())

    def test_senha_vazia_preserva_senha_atual(self):
        response = self.editar(password='')

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('senha-original'))

    def test_nova_senha_substitui_anterior(self):
        response = self.editar(password='senha-nova')

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('senha-nova'))
        self.assertFalse(self.usuario.check_password('senha-original'))

    def test_admin_permanece_autenticado_ao_alterar_propria_senha(self):
        self.url = reverse('core:editar_usuario', args=[self.admin.id])

        response = self.editar(
            username='admin-edicao',
            password='nova-senha-admin',
        )

        self.assertEqual(response.status_code, 200)
        pagina = self.client.get(reverse('core:acessos'))
        self.assertEqual(pagina.status_code, 200)

    def test_salva_zero_um_ou_varios_setores(self):
        response = self.editar(setor_ids=[self.setor_corte.id, self.setor_solda.id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(self.profile.setores.values_list('id', flat=True)),
            {self.setor_corte.id, self.setor_solda.id},
        )

        response = self.editar(setor_ids=[])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.profile.setores.exists())

    def test_rejeita_setor_invalido(self):
        response = self.editar(setor_ids=[999999])

        self.assertEqual(response.status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'usuario-edicao')

    def test_template_exibe_edicao_e_checkboxes_sem_select_multiplo(self):
        response = self.client.get(reverse('core:acessos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="editarUsuarioModal"')
        self.assertContains(response, 'onclick="openEditModal(${user.id})"', html=False)
        self.assertContains(response, 'id="novoSetoresList"')
        self.assertNotContains(response, 'id="novoSetores"')
        self.assertNotContains(response, 'id="userSectorList"')
