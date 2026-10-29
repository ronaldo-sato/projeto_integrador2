from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from django.contrib.auth.models import User

from farmacia.models import Farmacia
from medicamento.models import Medicamento
from .models import Preco

# Testes de proteção das views (login obrigatório)


class PrecoLoginObrigatorioTests(TestCase):

    def setUp(self):
        self.username = "usuario_teste"
        self.password = "senha_segura123"
        User.objects.create_user(
            username=self.username, password=self.password)

        self.farmacia = Farmacia.objects.create(
            nome='Farmácia Teste', endereco='Rua Teste, 1')
        self.medicamento = Medicamento.objects.create(
            nome='Dipirona', fabricante='Fabricante Teste')
        self.preco = Preco.objects.create(
            farmacia=self.farmacia, medicamento=self.medicamento,
            preco='10.50')

        self.url_cadastrar = reverse('preco:cadastrar')
        self.url_listar = reverse('preco:listar')
        self.url_atualizar = reverse(
            'preco:atualizar', args=[self.preco.id])
        self.url_deletar = reverse('preco:deletar', args=[self.preco.id])

    def url_login(self, url):
        """URL para onde o visitante é enviado ao acessar uma view
        protegida"""
        return f"{reverse('base:index')}?next={url}"

    def teste_visitante_nao_cadastra_preco(self):
        """Garantir que sem login não é possível cadastrar"""
        response = self.client.post(self.url_cadastrar, {
            'farmacia_id': self.farmacia.id,
            'medicamento_id': self.medicamento.id,
            'valor_preco': '0,01'})

        self.assertRedirects(response, self.url_login(self.url_cadastrar))
        self.assertEqual(Preco.objects.count(), 1)

    def teste_visitante_nao_lista_precos(self):
        """Garantir que sem login a listagem não é exibida"""
        response = self.client.get(self.url_listar)

        self.assertRedirects(response, self.url_login(self.url_listar))

    def teste_visitante_nao_atualiza_preco(self):
        """Garantir que sem login não é possível editar"""
        response = self.client.post(
            self.url_atualizar, {'valor_preco': '0,01'})

        self.assertRedirects(response, self.url_login(self.url_atualizar))
        self.preco.refresh_from_db()
        self.assertEqual(str(self.preco.preco), '10.50')

    def teste_visitante_nao_deleta_preco(self):
        """Garantir que sem login não é possível excluir"""
        response = self.client.post(self.url_deletar)

        self.assertRedirects(response, self.url_login(self.url_deletar))
        self.assertTrue(Preco.objects.filter(id=self.preco.id).exists())

    def teste_lista_mostra_a_ilustracao_do_medicamento(self):
        """Garantir que cada preço da lista mostra o desenho da forma do
        medicamento"""
        Medicamento.objects.filter(id=self.medicamento.id).update(
            nome='Dipirona Injetável')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        self.assertContains(
            response, 'ilustracao ilustracao-injetavel ilustracao-pequena')

    def teste_usuario_logado_cadastra_preco(self):
        """Garantir que com login o cadastro continua funcionando"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, {
            'medicamento_nome': 'Dipirona',
            'farmacia_id': self.farmacia.id,
            'medicamento_id': self.medicamento.id,
            'valor_preco': '12,34'})

        # Volta para a página de preços, onde aparece o novo preço
        self.assertRedirects(response, self.url_listar)
        self.assertTrue(Preco.objects.filter(preco='12.34').exists())

    def teste_usuario_logado_deleta_preco(self):
        """Garantir que com login a exclusão funciona e volta para a
        listagem de preços"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_deletar)

        self.assertRedirects(response, self.url_listar)
        self.assertFalse(Preco.objects.filter(id=self.preco.id).exists())

    def teste_usuario_logado_nao_deleta_por_link(self):
        """Garantir que a exclusão não acontece por GET (um link ou imagem
        de outro site não consegue apagar dados)"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_deletar)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Preco.objects.filter(id=self.preco.id).exists())

    def cadastrar_valor(self, valor):
        """Envia o formulário como a tela envia (medicamento, fabricante,
        farmácia e valor)"""
        self.client.login(username=self.username, password=self.password)
        return self.client.post(self.url_cadastrar, {
            'medicamento_nome': 'Dipirona',
            'farmacia_id': self.farmacia.id,
            'medicamento_id': self.medicamento.id,
            'valor_preco': valor})

    def teste_cadastro_recusa_fabricante_de_outro_medicamento(self):
        """Garantir que o preço não é gravado no medicamento errado quando
        o usuário troca o medicamento depois de filtrar as marcas"""
        Medicamento.objects.create(nome='Paracetamol', fabricante='Outra')
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, {
            'medicamento_nome': 'Paracetamol',
            'medicamento_id': self.medicamento.id,  # fabricante da Dipirona
            'farmacia_id': self.farmacia.id,
            'valor_preco': '5,00'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'O fabricante escolhido não é do medicamento')
        self.assertEqual(Preco.objects.count(), 1)

    def teste_cadastro_recusa_preco_negativo(self):
        """Garantir que um preço negativo não é gravado (ele apareceria
        como o menor preço na pesquisa)"""
        self.cadastrar_valor('-50')
        self.assertFalse(Preco.objects.filter(preco__lt=0).exists())

    def teste_cadastro_aceita_preco_zero(self):
        """Garantir que medicamento gratuito (preço zero) continua
        permitido"""
        self.cadastrar_valor('0')
        self.assertTrue(Preco.objects.filter(preco=0).exists())

    def teste_cadastro_recusa_valores_invalidos(self):
        """Garantir que valores que não são números válidos não são
        gravados"""
        for valor in ['nan', 'inf', 'abc', '1e30', '99999999']:
            self.cadastrar_valor(valor)
        self.assertEqual(Preco.objects.count(), 1)

    def teste_edicao_com_valores_invalidos_nao_quebra(self):
        """Garantir que a edição com valor inválido mostra erro em vez de
        gerar erro 500, e o preço original é mantido"""
        self.client.login(username=self.username, password=self.password)
        for valor in ['nan', 'inf', '99999999', '-1']:
            response = self.client.post(
                self.url_atualizar, {'valor_preco': valor})
            self.assertEqual(response.status_code, 200)

        self.preco.refresh_from_db()
        self.assertEqual(str(self.preco.preco), '10.50')

    def teste_edicao_aceita_virgula(self):
        """Garantir que o valor digitado com vírgula continua aceito"""
        self.client.login(username=self.username, password=self.password)
        self.client.post(self.url_atualizar, {'valor_preco': '7,25'})

        self.preco.refresh_from_db()
        self.assertEqual(str(self.preco.preco), '7.25')

    def teste_erro_no_cadastro_mantem_secao_e_dados(self):
        """Garantir que após um erro (preço negativo) a página de preços
        continua aberta com medicamento, fabricante, valor e farmácia
        ainda selecionados, para corrigir só o valor"""
        response = self.cadastrar_valor('-10')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Valor de preço inválido.')
        self.assertTemplateUsed(response, 'preco/listar.html')
        self.assertContains(response, 'data-foco="valor-preco"')
        self.assertContains(response, 'value="-10"')
        # Cada campo é verificado dentro do seu próprio <select> (sem
        # passar do </select>, já que os ids de teste podem coincidir)
        corpo = response.content.decode()
        dentro_do_select = r'(?:(?!</select>).)*?'
        self.assertRegex(
            corpo, r'(?s)<select id="select-farmacia"' + dentro_do_select +
            rf'value="{self.farmacia.id}" selected')
        self.assertRegex(
            corpo, r'(?s)<select id="select-fabricante"' + dentro_do_select +
            rf'value="{self.medicamento.id}" selected')
        self.assertEqual(Preco.objects.count(), 1)

    def teste_filtrar_marcas_mantem_dados_e_lista_fabricantes(self):
        """Garantir que o filtro de marcas pelo servidor (usado quando o
        navegador está sem JavaScript) carrega os fabricantes do
        medicamento sem perder o valor e a farmácia já preenchidos"""
        Medicamento.objects.create(nome='Dipirona', fabricante='Outra Marca')
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, {
            'acao_botao': 'filtrar',
            'medicamento_nome': 'Dipirona',
            'farmacia_id': self.farmacia.id,
            'valor_preco': '12,50'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-foco="select-fabricante"')
        self.assertContains(response, 'Selecione o fabricante')
        self.assertContains(response, 'Fabricante Teste')
        self.assertContains(response, 'Outra Marca')
        self.assertContains(response, 'value="12,50"')
        self.assertContains(
            response, f'value="{self.farmacia.id}" selected')
        self.assertEqual(Preco.objects.count(), 1)

    def teste_filtrar_marcas_sem_medicamento_avisa(self):
        """Garantir que filtrar sem escolher o medicamento mostra um aviso
        em vez de não fazer nada"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.url_cadastrar, {'acao_botao': 'filtrar'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'Selecione um medicamento antes de filtrar as marcas.')

    def teste_pagina_envia_fabricantes_para_o_javascript(self):
        """Garantir que a página envia a lista de fabricantes (usada para
        trocar as marcas sem recarregar) e mantém o botão de filtrar pelo
        servidor para navegadores sem JavaScript"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        self.assertContains(response, '<script id="dados-fabricantes"')
        self.assertContains(response, '"fabricante": "Fabricante Teste"')
        self.assertContains(response, '<noscript>')
        self.assertContains(response, 'value="filtrar"')

    def teste_lista_de_fabricantes_no_javascript_e_escapada(self):
        """Garantir que um nome malicioso na lista de fabricantes não fecha
        a tag <script> da página (XSS)"""
        Medicamento.objects.create(
            nome='Dipirona', fabricante='</script><script>alert(1)</script>')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        self.assertNotContains(response, '</script><script>alert(1)')

    def teste_sem_farmacia_cadastrada_explica_o_que_falta(self):
        """Garantir que sem farmácias a página explica o que cadastrar
        antes, em vez de mostrar um formulário impossível de usar"""
        Farmacia.objects.all().delete()
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        self.assertContains(response, 'Para registrar um preço é preciso')
        self.assertNotContains(response, 'id="formulario-preco"')

    def teste_exclusao_mostra_mensagem(self):
        """Garantir que a exclusão de um preço confirma o que aconteceu"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_deletar, follow=True)

        self.assertContains(response, 'Preço removido com sucesso!')
