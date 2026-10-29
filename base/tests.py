from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from django.contrib.auth.models import User

# Testes de Autenticação


class AutenticacaoTests(TestCase):

    def setUp(self):
        # Configurar usuário de teste no banco de dados temporário antes
        # de rodar os testes
        self.username = "usuario_teste"
        self.password = "senha_segura123"
        self.email = "teste@email.com"
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )
        # Caminhos das URLs testadas
        self.url_index = reverse('base:index')
        self.url_login = reverse('base:login')
        self.url_logout = reverse('base:logout')
        self.url_register = reverse('base:register')

    def teste_pagina_inicial_carrega_com_sucesso(self):
        """Garantir que a página abra normalmente (Status 200)"""
        response = self.client.get(self.url_index)
        self.assertEqual(response.status_code, 200)

    def teste_login_com_dados_corretos(self):
        """Garantir que o usuário consegue logar com credenciais
        válidas"""
        dados_login = {
            'username': self.username,
            'password': self.password
        }
        response = self.client.post(self.url_login, dados_login)

        # Após logar, Django deve redirecionar para o index
        self.assertRedirects(response, self.url_index)

        # Verifica se o usuário foi autenticado na sessão do cliente de
        # teste
        self.assertIn('_auth_user_id', self.client.session)

    def teste_login_com_dados_incorretos(self):
        """Garantir que o sistema nege o acesso se a senha estiver
        errada"""
        dados_errados = {
            'username': self.username,
            'password': 'senha_errada_qualquer'
        }
        response = self.client.post(self.url_login, dados_errados)

        # Deve continuar na página, com o modal de login reaberto e o
        # usuário já preenchido para corrigir só a senha
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário ou senha incorretos.')
        self.assertContains(response, 'data-aba-aberta="login"')
        self.assertContains(response, f'value="{self.username}"')

        # Garantir que o usuário não está logado na sessão
        self.assertNotIn('_auth_user_id', self.client.session)

    def teste_cadastro_de_novo_usuario(self):
        """Garantir que um novo usuário consegue se registrar com
        sucesso"""
        novos_dados = {
            'username': 'novo_usuario',
            'email': 'novo@email.com',
            'password': 'outrasenha123'
        }
        response = self.client.post(self.url_register, novos_dados)

        # Verifica o redirecionamento e se o usuário passou a existir no
        # banco
        self.assertRedirects(response, self.url_index)
        self.assertTrue(User.objects.filter(username='novo_usuario').exists())

    def teste_logout_limpa_sessao(self):
        """Garante que ao clicar em sair, a sessão é encerrada"""
        # Força o login do usuário primeiro
        self.client.login(username=self.username, password=self.password)

        # Faz a requisição de logout (somente POST)
        response = self.client.post(self.url_logout)

        self.assertRedirects(response, self.url_index)
        # Garante que as credenciais saíram da sessão
        self.assertNotIn('_auth_user_id', self.client.session)


# Testes de segurança (auditoria)


class SegurancaAutenticacaoTests(TestCase):

    def setUp(self):
        self.url_register = reverse('base:register')
        self.url_logout = reverse('base:logout')

    def cadastrar(self, username, email, password):
        return self.client.post(self.url_register, {
            'username': username, 'email': email, 'password': password})

    def teste_cadastro_recusa_senha_fraca(self):
        """Garantir que as regras de senha do settings.py são aplicadas"""
        self.cadastrar('fraco', 'fraco@email.com', '1')
        self.assertFalse(User.objects.filter(username='fraco').exists())

    def teste_cadastro_recusa_senha_vazia(self):
        """Garantir que não é possível criar conta sem senha"""
        self.cadastrar('vazio', 'vazio@email.com', '')
        self.assertFalse(User.objects.filter(username='vazio').exists())

    def teste_cadastro_recusa_email_invalido(self):
        """Garantir que o e-mail precisa ter formato válido"""
        self.cadastrar('semmail', 'isso-nao-e-email', 'senha_segura123')
        self.assertFalse(User.objects.filter(username='semmail').exists())

    def teste_cadastro_sem_campos_nao_quebra(self):
        """Garantir que um envio sem campos não gera erro 500"""
        response = self.client.post(self.url_register, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preencha usuário, e-mail e senha.')

    def teste_cadastro_usuario_muito_longo_nao_quebra(self):
        """Garantir que um nome de usuário gigante não gera erro 500"""
        response = self.cadastrar('a' * 300, 'longo@email.com',
                                  'senha_segura123')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='longo@email.com').exists())

    def teste_erro_no_cadastro_mantem_dados_menos_a_senha(self):
        """Garantir que após um erro o modal de cadastro reabre com usuário
        e e-mail preenchidos, mas a senha nunca volta para a página"""
        response = self.cadastrar('fraco', 'fraco@email.com', 'abc')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-aba-aberta="register"')
        self.assertContains(response, 'value="fraco"')
        self.assertContains(response, 'value="fraco@email.com"')
        self.assertNotContains(response, 'value="abc"')

    def teste_home_esconde_entrar_e_cadastrar_quando_logado(self):
        """Garantir que o usuário logado não vê os botões de entrar e
        cadastrar, e volta a vê-los depois de sair"""
        User.objects.create_user(username='logado', password='senha_segura123')
        self.client.login(username='logado', password='senha_segura123')

        response = self.client.get(reverse('base:index'))
        self.assertNotContains(response, 'id="btn-home-login"')
        self.assertNotContains(response, 'id="btn-home-register"')
        self.assertNotContains(response, 'id="auth-modal"')
        self.assertContains(response, 'Olá, logado!')

        self.client.post(self.url_logout)
        response = self.client.get(reverse('base:index'))
        self.assertContains(response, 'id="btn-home-login"')
        self.assertContains(response, 'id="btn-home-register"')

    def teste_logout_por_link_nao_desloga(self):
        """Garantir que o logout não acontece por GET (um link ou imagem
        de outro site não consegue deslogar o usuário)"""
        User.objects.create_user(username='logado', password='senha_segura123')
        self.client.login(username='logado', password='senha_segura123')

        response = self.client.get(self.url_logout)

        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def teste_login_volta_para_a_pagina_que_o_usuario_tentou_abrir(self):
        """Garantir que, após entrar, o usuário volta para a página que
        tentou abrir sem estar logado"""
        User.objects.create_user(username='logado', password='senha_segura123')
        response = self.client.post(reverse('base:login'), {
            'username': 'logado', 'password': 'senha_segura123',
            'next': reverse('farmacia:listar')})

        self.assertRedirects(response, reverse('farmacia:listar'))

    def teste_login_nao_redireciona_para_outro_site(self):
        """Garantir que um link malicioso (?next=https://outro-site) não
        leva o usuário para fora da aplicação após o login"""
        User.objects.create_user(username='logado', password='senha_segura123')
        response = self.client.post(reverse('base:login'), {
            'username': 'logado', 'password': 'senha_segura123',
            'next': 'https://site-falso.com/'})

        self.assertRedirects(response, reverse('base:index'))

    def teste_pagina_protegida_abre_a_janela_de_login(self):
        """Garantir que ao tentar abrir uma página que exige login, a home
        já abre a janela de login com o destino guardado"""
        response = self.client.get(reverse('farmacia:listar'), follow=True)

        self.assertContains(response, 'data-aba-aberta="login"')
        self.assertContains(
            response, f'name="next" value="{reverse("farmacia:listar")}"')


# Configuração do deploy

from project.settings import banco_da_url


class ConfiguracaoDeployTests(TestCase):

    def teste_endereco_do_banco_no_formato_do_neon(self):
        """Garantir que o DATABASE_URL do Neon vira a configuração do Django,
        inclusive com caracteres especiais na senha e o SSL obrigatório"""
        banco = banco_da_url(
            'postgresql://neondb_owner:s%40nh%2Fa@ep-abc-123.us-east-1.aws.neon.tech'
            '/neondb?sslmode=require&channel_binding=require')

        self.assertEqual(banco['NAME'], 'neondb')
        self.assertEqual(banco['USER'], 'neondb_owner')
        self.assertEqual(banco['PASSWORD'], 's@nh/a')
        self.assertEqual(banco['HOST'], 'ep-abc-123.us-east-1.aws.neon.tech')
        self.assertEqual(banco['PORT'], '5432')
        self.assertEqual(banco['OPTIONS'],
                         {'sslmode': 'require', 'channel_binding': 'require'})

    def teste_endereco_do_banco_mal_colado_e_recusado(self):
        """Garantir que um endereço inválido dá erro claro (em vez de o
        Django tentar o banco local sem senha)"""
        from django.core.exceptions import ImproperlyConfigured
        for errado in ('cole_aqui_o_endereco_do_neon',
                       "psql 'postgresql://u:s@ep-x.aws.neon.tech/neondb'"):
            with self.subTest(errado=errado), \
                    self.assertRaises(ImproperlyConfigured):
                banco_da_url(errado)
