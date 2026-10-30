from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from django.contrib.auth.models import User

from farmacia.models import EstabelecimentoMapa, Farmacia
from medicamento.models import Medicamento
from preco.models import Preco

# Testes de proteção das views (login obrigatório)


class PesquisaLoginObrigatorioTests(TestCase):

    def setUp(self):
        self.username = "usuario_teste"
        self.password = "senha_segura123"
        User.objects.create_user(
            username=self.username, password=self.password)

        farmacia = Farmacia.objects.create(
            nome='Farmácia Teste', endereco='Rua Teste, 1')
        medicamento = Medicamento.objects.create(
            nome='Dipirona', fabricante='Fabricante Teste')
        Preco.objects.create(
            farmacia=farmacia, medicamento=medicamento, preco='10.50')

        self.url_pesquisa = reverse('pesquisa:precos')

    def teste_visitante_nao_pesquisa(self):
        """Garantir que sem login a pesquisa não é feita"""
        response = self.client.get(self.url_pesquisa)

        self.assertRedirects(
            response, f"{reverse('base:index')}?next={self.url_pesquisa}")

    def teste_usuario_logado_pesquisa(self):
        """Garantir que com login a pesquisa retorna os preços (sem
        diferenciar maiúsculas e minúsculas)"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(
            self.url_pesquisa, {'medicamento_nome': 'dipirona'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Farmácia Teste')

    def teste_primeira_visita_mostra_so_o_formulario(self):
        """Garantir que abrir a página sem pesquisar mostra o formulário,
        sem mensagem de erro"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_pesquisa)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="formulario-pesquisa"')
        self.assertNotContains(
            response, 'Selecione um medicamento para pesquisar.')

    def teste_pesquisa_sem_medicamento_mostra_erro(self):
        """Garantir que pesquisar sem escolher o medicamento mostra o erro
        na própria página de pesquisa"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(
            self.url_pesquisa, {'medicamento_nome': ''})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'Selecione um medicamento para pesquisar.')
        self.assertTemplateUsed(response, 'pesquisa/precos.html')

    def teste_menor_preco_considera_o_registro_mais_recente(self):
        """Garantir a regra da pesquisa: para cada farmácia e marca vale o
        preço mais recente; o menor deles fica em destaque"""
        farmacia = Farmacia.objects.get(nome='Farmácia Teste')
        medicamento = Medicamento.objects.get(nome='Dipirona')
        outra = Farmacia.objects.create(nome='Outra Farmácia', endereco='E2')
        # Preço mais recente da Farmácia Teste: 9,00 (o 10,50 é antigo)
        Preco.objects.create(
            farmacia=farmacia, medicamento=medicamento, preco='9.00')
        Preco.objects.create(
            farmacia=outra, medicamento=medicamento, preco='12.00')

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(
            self.url_pesquisa, {'medicamento_nome': 'Dipirona'})

        precos = [p.preco for p in response.context['precos']]
        self.assertEqual([str(p) for p in precos], ['9.00', '12.00'])
        self.assertEqual(str(response.context['menor_preco']), '9.00')
        self.assertEqual(str(response.context['economia']), '3.00')
        self.assertContains(response, 'Menor preço', count=2)  # card + selo

    def teste_resultado_mostra_a_ilustracao_do_medicamento(self):
        """Garantir que o resultado mostra o desenho da forma do medicamento
        (Dipirona não diz a forma no nome: desenho genérico)"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_pesquisa, {'medicamento_nome': 'Dipirona'})

        self.assertEqual(response.context['forma'].chave, 'medicamento')
        self.assertContains(response, 'ilustracao ilustracao-medicamento ilustracao-grande')

        Medicamento.objects.filter(nome='Dipirona').update(nome='Dipirona Gotas')
        response = self.client.get(self.url_pesquisa, {'medicamento_nome': 'Dipirona Gotas'})
        self.assertEqual(response.context['forma'].rotulo, 'Gotas / colírio')

    def teste_resultado_tem_link_do_google_maps(self):
        """Garantir que cada estabelecimento do resultado tem o link para
        abrir no Google Maps (no card de menor preço e na tabela)"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_pesquisa, {'medicamento_nome': 'Dipirona'})

        self.assertContains(
            response,
            'href="https://www.google.com/maps/search/?api=1&amp;query='
            'Farm%C3%A1cia+Teste%2C+Rua+Teste%2C+1"', count=2)

    def teste_selo_registrado_no_mapa_no_resultado(self):
        """Garantir que o resultado indica os estabelecimentos com registro
        ativo no MAPA (pelo CNPJ) e só eles"""
        farmacia = Farmacia.objects.get(nome='Farmácia Teste')
        farmacia.cnpj = '00020617000179'
        farmacia.save()
        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.url_pesquisa, {'medicamento_nome': 'Dipirona'})
        self.assertNotContains(response, 'Registrado no MAPA')

        EstabelecimentoMapa.objects.create(
            cnpj='00020617000179', razao_social='X', situacao='ativo',
            atividades='COMERCIANTE')
        response = self.client.get(self.url_pesquisa, {'medicamento_nome': 'Dipirona'})
        # No cartão do menor preço e na linha da tabela
        self.assertContains(response, 'Registrado no MAPA', count=2)
