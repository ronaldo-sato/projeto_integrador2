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

        # Deve redirecionar de volta para o index para mostrar o erro
        self.assertRedirects(response, self.url_index)

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

        # Faz a requisição de logout
        response = self.client.get(self.url_logout)

        self.assertRedirects(response, self.url_index)
        # Garante que as credenciais saíram da sessão
        self.assertNotIn('_auth_user_id', self.client.session)
