import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cadastro.models import Setor
from core.models import Profile, RotaAcesso

from .models import Report


class ReportConclusaoTests(TestCase):
    def setUp(self):
        self.pcp = User.objects.create_user(username='pcp', password='senha')
        Profile.objects.create(user=self.pcp, tipo_acesso='pcp')

        self.admin = User.objects.create_user(username='admin', password='senha')
        Profile.objects.create(user=self.admin, tipo_acesso='admin')

        self.operador = User.objects.create_user(username='operador', password='senha')
        Profile.objects.create(user=self.operador, tipo_acesso='operador')

        self.report = Report.objects.create(
            usuario=self.operador,
            texto='Report de teste',
            data=date.today(),
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
        self.assertTrue(response.json()[0]['concluido'])

    def test_listagem_retorna_apenas_reports_de_hoje(self):
        Report.objects.create(
            usuario=self.operador,
            texto='Report histórico',
            data=date(2026, 1, 10),
        )
        self.client.force_login(self.operador)

        response = self.client.get(reverse('reuniao:listar_reports'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['id'], self.report.id)

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

    def test_usuario_sem_setor_cria_report_sem_setor(self):
        response = self.criar_report()

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['setor'])
        self.assertIsNone(Report.objects.get(pk=response.json()['id']).setor)

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

    def test_filtros_todos_setor_e_sem_setor(self):
        report_corte = Report.objects.create(
            usuario=self.usuario,
            texto='Corte',
            data=date.today(),
            setor=self.setor_corte,
        )
        report_solda = Report.objects.create(
            usuario=self.usuario,
            texto='Solda',
            data=date.today(),
            setor=self.setor_solda,
        )
        report_sem_setor = Report.objects.create(
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

        todos = self.client.get(self.listar_url).json()
        corte = self.client.get(
            self.listar_url,
            {'setor': self.setor_corte.id},
        ).json()
        sem_setor = self.client.get(
            self.listar_url,
            {'setor': 'sem-setor'},
        ).json()

        self.assertEqual(
            {item['id'] for item in todos},
            {report_corte.id, report_solda.id, report_sem_setor.id},
        )
        self.assertEqual([item['id'] for item in corte], [report_corte.id])
        self.assertEqual([item['id'] for item in sem_setor], [report_sem_setor.id])

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
