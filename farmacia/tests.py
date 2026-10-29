import io
import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from django.contrib.auth.models import User

from . import cep
from .models import Farmacia, montar_endereco


def dados_formulario(**alteracoes):
    """Dados válidos do formulário de estabelecimento (com alterações)"""
    dados = {
        'nome_farmacia': 'Pet Shop Novo',
        'tipo': 'petshop',
        'cep': '01310100',
        'logradouro': 'Avenida Paulista',
        'numero': '1000',
        'complemento': '',
        'bairro': 'Bela Vista',
        'cidade': 'São Paulo',
        'uf': 'SP',
    }
    dados.update(alteracoes)
    return dados


# Testes de proteção das views (login obrigatório)


class FarmaciaLoginObrigatorioTests(TestCase):

    def setUp(self):
        self.username = "usuario_teste"
        self.password = "senha_segura123"
        User.objects.create_user(
            username=self.username, password=self.password)

        self.farmacia = Farmacia.objects.create(
            nome='Farmácia Teste', endereco='Rua Teste, 1')

        self.url_cadastrar = reverse('farmacia:cadastrar')
        self.url_listar = reverse('farmacia:listar')
        self.url_atualizar = reverse(
            'farmacia:atualizar', args=[self.farmacia.id])
        self.url_deletar = reverse(
            'farmacia:deletar', args=[self.farmacia.id])

    def url_login(self, url):
        """URL para onde o visitante é enviado ao acessar uma view
        protegida"""
        return f"{reverse('base:index')}?next={url}"

    def teste_visitante_nao_cadastra_farmacia(self):
        """Garantir que sem login não é possível cadastrar"""
        response = self.client.post(
            self.url_cadastrar, dados_formulario(nome_farmacia='Intrusa'))

        self.assertRedirects(response, self.url_login(self.url_cadastrar))
        self.assertFalse(Farmacia.objects.filter(nome='Intrusa').exists())

    def teste_visitante_nao_lista_farmacias(self):
        """Garantir que sem login a listagem não é exibida"""
        response = self.client.get(self.url_listar)

        self.assertRedirects(response, self.url_login(self.url_listar))

    def teste_visitante_nao_atualiza_farmacia(self):
        """Garantir que sem login não é possível editar"""
        response = self.client.post(
            self.url_atualizar, dados_formulario(nome_farmacia='Alterado'))

        self.assertRedirects(response, self.url_login(self.url_atualizar))
        self.farmacia.refresh_from_db()
        self.assertEqual(self.farmacia.nome, 'Farmácia Teste')

    def teste_visitante_nao_deleta_farmacia(self):
        """Garantir que sem login não é possível excluir"""
        response = self.client.post(self.url_deletar)

        self.assertRedirects(response, self.url_login(self.url_deletar))
        self.assertTrue(
            Farmacia.objects.filter(id=self.farmacia.id).exists())

    def teste_visitante_nao_consulta_cep(self):
        """Garantir que a consulta de CEP também exige login"""
        url = reverse('farmacia:buscar_cep', args=['01310100'])
        response = self.client.get(url)

        self.assertRedirects(response, self.url_login(url))

    def teste_usuario_logado_cadastra_farmacia(self):
        """Garantir que com login o cadastro continua funcionando"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, dados_formulario())

        # Volta para a página de estabelecimentos, onde aparece o novo
        self.assertRedirects(response, self.url_listar)
        self.assertTrue(
            Farmacia.objects.filter(nome='Pet Shop Novo').exists())

    def teste_usuario_logado_lista_farmacias(self):
        """Garantir que com login a listagem é exibida"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Farmácia Teste')

    def teste_usuario_logado_deleta_farmacia(self):
        """Garantir que com login a exclusão continua funcionando"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_deletar)

        self.assertRedirects(response, self.url_listar)
        self.assertFalse(
            Farmacia.objects.filter(id=self.farmacia.id).exists())

    def teste_usuario_logado_nao_deleta_por_link(self):
        """Garantir que a exclusão não acontece por GET (um link ou imagem
        de outro site não consegue apagar dados)"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_deletar)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            Farmacia.objects.filter(id=self.farmacia.id).exists())

    def teste_listagem_nao_executa_script_do_nome(self):
        """Garantir que um nome malicioso não vira código JavaScript no
        botão de confirmação (XSS)"""
        Farmacia.objects.create(
            nome="x');alert('XSS');//", endereco='Rua Teste, 2')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        corpo = response.content.decode()
        # A página não tem JavaScript embutido no HTML (onclick, onsubmit...):
        # a confirmação usa o atributo data-confirmar, inserido como texto
        self.assertNotRegex(corpo, r'\son[a-z]+\s*=')
        # E o nome aparece escapado (as aspas não "fecham" o atributo)
        self.assertIn('x&#x27;);alert(&#x27;XSS&#x27;);//', corpo)
        self.assertNotIn("x');alert('XSS');//", corpo)


# Testes do cadastro de estabelecimentos (regras de negócio)


class CadastroEstabelecimentoTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')
        self.url_cadastrar = reverse('farmacia:cadastrar')
        self.url_listar = reverse('farmacia:listar')

    def cadastrar(self, **alteracoes):
        return self.client.post(
            self.url_cadastrar, dados_formulario(**alteracoes))

    def teste_cadastro_monta_o_endereco_completo(self):
        """Garantir que as partes do endereço são salvas e o endereço
        completo é montado em uma linha"""
        self.cadastrar(complemento='Loja 3')
        farmacia = Farmacia.objects.get(nome='Pet Shop Novo')

        self.assertEqual(farmacia.tipo, 'petshop')
        self.assertEqual(farmacia.cep, '01310-100')
        self.assertEqual(
            farmacia.endereco,
            'Avenida Paulista, 1000 - Loja 3 - Bela Vista, São Paulo/SP')

    def teste_cep_e_opcional(self):
        """Garantir que dá para cadastrar sem CEP (se a busca estiver fora
        do ar, o usuário preenche o endereço manualmente)"""
        response = self.cadastrar(cep='')

        self.assertRedirects(response, self.url_listar)
        self.assertEqual(Farmacia.objects.get().cep, '')

    def teste_unidades_da_mesma_rede_em_enderecos_diferentes(self):
        """Garantir que a mesma rede pode ter várias unidades: mesmo nome,
        endereços diferentes"""
        self.cadastrar(nome_farmacia='Rede Pet', numero='100')
        response = self.cadastrar(nome_farmacia='Rede Pet', numero='200')

        self.assertRedirects(response, self.url_listar)
        self.assertEqual(Farmacia.objects.filter(nome='Rede Pet').count(), 2)

    def teste_mesmo_nome_no_mesmo_endereco_e_recusado(self):
        """Garantir que não se cadastra o mesmo estabelecimento duas vezes
        (mesmo nome e mesmo endereço, sem diferenciar maiúsculas)"""
        self.cadastrar(nome_farmacia='Rede Pet')
        response = self.cadastrar(nome_farmacia='REDE PET')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já está cadastrado!')
        self.assertEqual(Farmacia.objects.count(), 1)

    def teste_campos_obrigatorios(self):
        """Garantir que faltando campos obrigatórios nada é gravado e o
        erro diz o que falta"""
        response = self.cadastrar(numero='', bairro='')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preencha o número, o bairro.')
        self.assertFalse(Farmacia.objects.exists())

    def teste_envio_sem_campos_nao_quebra(self):
        """Garantir que um envio sem nenhum campo não gera erro 500"""
        response = self.client.post(self.url_cadastrar, {})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Farmacia.objects.exists())

    def teste_tipo_uf_e_cep_invalidos_sao_recusados(self):
        """Garantir que valores fora das opções não são gravados"""
        for alteracao, mensagem in [
                ({'tipo': 'hospital'}, 'tipo de estabelecimento válido'),
                ({'uf': 'XX'}, 'UF válida'),
                ({'cep': '123'}, 'O CEP deve ter 8 dígitos')]:
            response = self.cadastrar(**alteracao)
            self.assertContains(response, mensagem)
        self.assertFalse(Farmacia.objects.exists())

    def teste_campo_maior_que_o_banco_nao_quebra(self):
        """Garantir que um texto maior que o limite do banco mostra erro em
        vez de gerar erro 500"""
        response = self.cadastrar(nome_farmacia='x' * 150)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no máximo 100 caracteres')
        self.assertFalse(Farmacia.objects.exists())

    def teste_erro_mantem_os_dados_digitados(self):
        """Garantir que após um erro a página continua aberta com tudo o
        que o usuário já tinha preenchido"""
        response = self.cadastrar(numero='')

        self.assertTemplateUsed(response, 'farmacia/listar.html')
        self.assertContains(response, 'value="Pet Shop Novo"')
        self.assertContains(response, 'value="Avenida Paulista"')
        self.assertRegex(response.content.decode(),
                         r'id="tipo-petshop" value="petshop"[^>]*checked')
        self.assertContains(response, '<option value="SP" selected>')

    def teste_edicao_com_erro_mantem_o_que_foi_digitado(self):
        """Garantir que um erro na edição mantém o texto digitado em vez
        de voltar aos dados originais"""
        self.cadastrar()
        farmacia = Farmacia.objects.get()
        response = self.client.post(
            reverse('farmacia:atualizar', args=[farmacia.id]),
            dados_formulario(nome_farmacia='Nome Corrigido', bairro=''))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Nome Corrigido"')

    def teste_edicao_atualiza_o_endereco(self):
        """Garantir que editar o número atualiza o endereço completo"""
        self.cadastrar()
        farmacia = Farmacia.objects.get()
        self.client.post(reverse('farmacia:atualizar', args=[farmacia.id]),
                         dados_formulario(numero='2000'))

        farmacia.refresh_from_db()
        self.assertIn('Avenida Paulista, 2000', farmacia.endereco)

    def teste_edicao_nao_pode_duplicar_outra_unidade(self):
        """Garantir que a edição não deixa uma unidade ficar igual a outra
        (mesmo nome e endereço)"""
        self.cadastrar(numero='100')
        self.cadastrar(numero='200')
        segunda = Farmacia.objects.get(numero='200')
        response = self.client.post(
            reverse('farmacia:atualizar', args=[segunda.id]),
            dados_formulario(numero='100'))

        self.assertContains(response, 'Já existe')
        segunda.refresh_from_db()
        self.assertEqual(segunda.numero, '200')

    def teste_montar_endereco_sem_complemento(self):
        """Garantir o formato do endereço quando não há complemento"""
        self.assertEqual(
            montar_endereco('Rua A', '10', '', 'Centro', 'Campinas', 'SP'),
            'Rua A, 10 - Centro, Campinas/SP')


# Testes da consulta de CEP (as APIs externas são simuladas: os testes não
# dependem de internet)


def resposta_json(dados):
    """Simula a resposta de urlopen com o JSON informado"""
    return BytesIO(json.dumps(dados).encode('utf-8'))


VIACEP_PAULISTA = {
    'cep': '01310-100', 'logradouro': 'Avenida Paulista',
    'bairro': 'Bela Vista', 'localidade': 'São Paulo', 'uf': 'SP'}
BRASILAPI_PAULISTA = {
    'cep': '01310100', 'street': 'Avenida Paulista',
    'neighborhood': 'Bela Vista', 'city': 'São Paulo', 'state': 'SP'}
ENDERECO_PAULISTA = {
    'cep': '01310-100', 'logradouro': 'Avenida Paulista',
    'bairro': 'Bela Vista', 'cidade': 'São Paulo', 'uf': 'SP'}


@patch('farmacia.cep.urlopen')
class ConsultaCepTests(TestCase):

    def setUp(self):
        cache.clear()

    def teste_consulta_na_viacep(self, urlopen):
        """Garantir que o endereço vem da ViaCEP no formato do sistema"""
        urlopen.return_value = resposta_json(VIACEP_PAULISTA)

        self.assertEqual(cep.consultar_cep('01310-100'), ENDERECO_PAULISTA)
        self.assertIn('viacep.com.br/ws/01310100/',
                      urlopen.call_args[0][0].full_url)

    def teste_usa_brasilapi_se_a_viacep_falhar(self, urlopen):
        """Garantir que, com a ViaCEP fora do ar, a BrasilAPI é usada"""
        urlopen.side_effect = [URLError('fora do ar'),
                               resposta_json(BRASILAPI_PAULISTA)]

        self.assertEqual(cep.consultar_cep('01310100'), ENDERECO_PAULISTA)
        self.assertIn('brasilapi.com.br',
                      urlopen.call_args[0][0].full_url)

    def teste_cep_inexistente(self, urlopen):
        """Garantir que um CEP que nenhuma das APIs conhece é informado
        como inexistente"""
        urlopen.side_effect = [resposta_json({'erro': 'true'}),
                               HTTPError('url', 404, 'Not Found', {}, None)]

        with self.assertRaises(cep.CepNaoEncontrado):
            cep.consultar_cep('99999999')

    def teste_cep_que_falta_na_viacep_e_buscado_na_brasilapi(self, urlopen):
        """Caso real: o CEP geral de São Pedro/SP (13520-000) não existe na
        ViaCEP, mas existe na BrasilAPI"""
        urlopen.side_effect = [
            resposta_json({'erro': 'true'}),
            resposta_json({'cep': '13520000', 'street': '', 'neighborhood': '',
                           'city': 'São Pedro', 'state': 'SP'})]

        endereco = cep.consultar_cep('13520-000')
        self.assertEqual(endereco['cidade'], 'São Pedro')
        self.assertEqual(endereco['logradouro'], '')

    def teste_cep_inexistente_na_brasilapi(self, urlopen):
        """Garantir que o 404 da BrasilAPI significa CEP inexistente"""
        urlopen.side_effect = [
            URLError('fora do ar'),
            HTTPError('url', 404, 'Not Found', {}, None)]

        with self.assertRaises(cep.CepNaoEncontrado):
            cep.consultar_cep('99999999')

    def teste_as_duas_apis_fora_do_ar(self, urlopen):
        """Garantir que sem nenhuma API o erro é de serviço indisponível"""
        urlopen.side_effect = URLError('sem internet')

        with self.assertRaises(cep.ServicoCepIndisponivel):
            cep.consultar_cep('01310100')

    def teste_cep_com_formato_invalido_nem_consulta(self, urlopen):
        """Garantir que um CEP sem 8 dígitos é recusado sem chamar a API"""
        with self.assertRaises(cep.CepInvalido):
            cep.consultar_cep('123')
        urlopen.assert_not_called()

    def teste_resultado_fica_em_cache(self, urlopen):
        """Garantir que o mesmo CEP não é consultado duas vezes na API"""
        urlopen.return_value = resposta_json(VIACEP_PAULISTA)
        cep.consultar_cep('01310100')
        cep.consultar_cep('01310-100')

        self.assertEqual(urlopen.call_count, 1)


@patch('farmacia.cep.urlopen')
class EndpointCepTests(TestCase):

    def setUp(self):
        cache.clear()
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')

    def buscar(self, valor):
        return self.client.get(reverse('farmacia:buscar_cep', args=[valor]))

    def teste_retorna_o_endereco_em_json(self, urlopen):
        urlopen.return_value = resposta_json(VIACEP_PAULISTA)
        response = self.buscar('01310100')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ENDERECO_PAULISTA)

    def teste_cep_invalido_retorna_400(self, urlopen):
        self.assertEqual(self.buscar('123').status_code, 400)

    def teste_cep_inexistente_retorna_404(self, urlopen):
        urlopen.side_effect = [resposta_json({'erro': 'true'}),
                               HTTPError('url', 404, 'Not Found', {}, None)]
        response = self.buscar('99999999')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['erro'], 'CEP não encontrado.')

    def teste_servico_fora_do_ar_retorna_503(self, urlopen):
        urlopen.side_effect = URLError('sem internet')

        self.assertEqual(self.buscar('01310100').status_code, 503)


# ---------------------------------------------------------------------------
# CNPJ, estabelecimentos registrados no MAPA e preenchimento do cadastro
# ---------------------------------------------------------------------------

from django.core.management import call_command

from . import cnpj as modulo_cnpj
from . import mapa as mapa_estabelecimentos
from . import sugestoes as sugestoes_estabelecimentos
from .models import EstabelecimentoMapa


def gerar_cnpj(base12):
    """CNPJ válido a partir dos 12 primeiros dígitos (calcula os verificadores)"""
    primeiro = modulo_cnpj._digito(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    segundo = modulo_cnpj._digito(base12 + primeiro, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return base12 + primeiro + segundo


CNPJ_PET = gerar_cnpj('123456780001')
CNPJ_AGRO = gerar_cnpj('987654320001')

RECEITA_PET = {
    'razao_social': 'PET AMIGO COMERCIO LTDA', 'nome_fantasia': 'PET SHOP AMIGO FIEL',
    'descricao_tipo_de_logradouro': 'AVENIDA', 'logradouro': 'PAULISTA', 'numero': '1000',
    'complemento': 'LOJA 2', 'bairro': 'BELA VISTA', 'cep': '01310100',
    'municipio': 'SAO PAULO', 'uf': 'SP', 'descricao_situacao_cadastral': 'ATIVA',
}

CSV_MAPA = (
    'UNIDADE_DA_FEDERACAO;MUNICIPIO;NUMERO_REGISTRO_ESTABELECIMENTO;STATUS_DO_REGISTRO;'
    'CNPJ;RAZAO_SOCIAL;NOME_FANTASIA;AREA_ATUACAO;ATIVIDADE;CLASSIFICACAO;CARACTERISTICA_ADICIONAL\r\n'
    f'SP;São Paulo;SP0001;Ativo;{CNPJ_PET};PET AMIGO COMERCIO LTDA;PET SHOP AMIGO FIEL;'
    'PRODUTO VETERINÁRIO;COMERCIANTE;PRODUTO FARMACÊUTICO;NÃO CONTROLADO\r\n'
    f'SP;São Paulo;SP0001;Cancelado;{CNPJ_PET};PET AMIGO COMERCIO LTDA;PET SHOP AMIGO FIEL;'
    'PRODUTO VETERINÁRIO;COMERCIANTE;PRODUTO BIOLÓGICO;OUTROS\r\n'
    f'RS;Canguçu;RS0002;Cancelado;{CNPJ_AGRO};AGROPECUARIA CAMPO SUL LTDA;********;'
    'PRODUTO VETERINÁRIO;COMERCIANTE;PRODUTO FARMACÊUTICO;OUTROS\r\n'
).encode('utf-8')


class ValidacaoCnpjTests(TestCase):

    def teste_cnpj_valido_e_invalido(self):
        self.assertTrue(modulo_cnpj.cnpj_valido(CNPJ_PET))
        self.assertTrue(modulo_cnpj.cnpj_valido(modulo_cnpj.formatar_cnpj(CNPJ_PET)))
        # Último dígito trocado, tamanho errado e números repetidos
        self.assertFalse(modulo_cnpj.cnpj_valido(CNPJ_PET[:-1] + str((int(CNPJ_PET[-1]) + 1) % 10)))
        self.assertFalse(modulo_cnpj.cnpj_valido('123'))
        self.assertFalse(modulo_cnpj.cnpj_valido('11111111111111'))

    def teste_formatacao(self):
        self.assertEqual(modulo_cnpj.formatar_cnpj('49475833000106'), '49.475.833/0001-06')
        self.assertEqual(modulo_cnpj.limpar_cnpj('49.475.833/0001-06'), '49475833000106')


@patch('farmacia.cnpj._buscar')
class ConsultaReceitaTests(TestCase):

    def setUp(self):
        cache.clear()

    def teste_monta_os_dados_da_receita(self, buscar):
        buscar.return_value = RECEITA_PET
        dados = modulo_cnpj.consultar_receita(CNPJ_PET)

        self.assertEqual(dados['logradouro'], 'AVENIDA PAULISTA')
        self.assertEqual(dados['cep'], '01310-100')
        self.assertEqual(dados['cidade'], 'SAO PAULO')
        self.assertEqual(dados['situacao'], 'ATIVA')

    def teste_usa_a_reserva_se_a_brasilapi_falhar(self, buscar):
        buscar.side_effect = [URLError('fora do ar'), RECEITA_PET]
        modulo_cnpj.consultar_receita(CNPJ_PET)

        self.assertIn('minhareceita.org', buscar.call_args[0][0])

    def teste_cnpj_invalido_nem_consulta(self, buscar):
        with self.assertRaises(modulo_cnpj.CnpjInvalido):
            modulo_cnpj.consultar_receita('12345678000100')
        buscar.assert_not_called()

    def teste_cnpj_inexistente(self, buscar):
        buscar.side_effect = HTTPError('url', 404, 'Not Found', {}, None)
        with self.assertRaises(modulo_cnpj.CnpjNaoEncontrado):
            modulo_cnpj.consultar_receita(CNPJ_PET)

    def teste_apis_fora_do_ar(self, buscar):
        buscar.side_effect = URLError('sem internet')
        with self.assertRaises(modulo_cnpj.ServicoCnpjIndisponivel):
            modulo_cnpj.consultar_receita(CNPJ_PET)


class EstabelecimentosMapaTests(TestCase):

    def importar(self):
        with patch('farmacia.mapa.url_do_csv', return_value='https://mapa/csv'), \
                patch('farmacia.mapa.baixar', return_value=CSV_MAPA):
            call_command('importar_estabelecimentos_mapa', stdout=io.StringIO())

    def teste_consolida_as_linhas_de_cada_cnpj(self):
        """Um CNPJ com uma linha ativa e outra cancelada continua ativo; as
        classificações das várias linhas são reunidas"""
        self.importar()
        pet = EstabelecimentoMapa.objects.get(cnpj=CNPJ_PET)
        agro = EstabelecimentoMapa.objects.get(cnpj=CNPJ_AGRO)

        self.assertEqual(EstabelecimentoMapa.objects.count(), 2)
        self.assertEqual(pet.situacao, 'ativo')
        self.assertEqual(pet.classificacoes, 'PRODUTO BIOLÓGICO, PRODUTO FARMACÊUTICO')
        self.assertEqual(agro.situacao, 'cancelado')

    def teste_nome_fantasia_mascarado_usa_a_razao_social(self):
        self.importar()
        agro = EstabelecimentoMapa.objects.get(cnpj=CNPJ_AGRO)

        self.assertEqual(agro.nome_fantasia, '')
        self.assertEqual(agro.nome, 'AGROPECUARIA CAMPO SUL LTDA')

    def teste_reimportar_substitui_os_dados(self):
        self.importar()
        self.importar()
        self.assertEqual(EstabelecimentoMapa.objects.count(), 2)

    def teste_sugere_o_tipo_pelo_nome(self):
        self.assertEqual(mapa_estabelecimentos.sugerir_tipo('Pet Shop Amigo'), 'petshop')
        self.assertEqual(mapa_estabelecimentos.sugerir_tipo('Agropecuária Bom Jesus'), 'agropecuaria')
        self.assertEqual(mapa_estabelecimentos.sugerir_tipo('Clínica Vet Care'), 'clinica')
        self.assertEqual(mapa_estabelecimentos.sugerir_tipo('Drogaria Vet'), 'farmacia')
        self.assertEqual(mapa_estabelecimentos.sugerir_tipo('Casa Silva', 'MANIPULADOR'), 'farmacia')
        self.assertEqual(mapa_estabelecimentos.sugerir_tipo('Casa Silva', 'COMERCIANTE'), '')


VIACEP_PAULISTA_LOJA = {
    'cep': '01310-100', 'logradouro': 'Avenida Paulista',
    'bairro': 'Bela Vista', 'localidade': 'São Paulo', 'uf': 'SP'}


class PreenchimentoPorCnpjTests(TestCase):

    def setUp(self):
        cache.clear()
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')
        EstabelecimentoMapa.objects.create(
            cnpj=CNPJ_PET, registro='SP0001', razao_social='PET AMIGO COMERCIO LTDA',
            nome_fantasia='PET SHOP AMIGO FIEL', municipio='São Paulo', uf='SP',
            situacao='ativo', atividades='COMERCIANTE')

    def consultar(self, cnpj, receita=RECEITA_PET, viacep=VIACEP_PAULISTA_LOJA):
        efeito_receita = receita if isinstance(receita, Exception) else None
        with patch('farmacia.cnpj._buscar', return_value=receita, side_effect=efeito_receita), \
                patch('farmacia.cep.urlopen', return_value=resposta_json(viacep)):
            return self.client.get(reverse('farmacia:buscar_cnpj', args=[cnpj]))

    def teste_junta_mapa_receita_e_cep(self):
        """Nome e registro vêm do MAPA, número e complemento da Receita, e o
        endereço bem escrito (com acentos) da consulta de CEP"""
        dados = self.consultar(CNPJ_PET).json()

        self.assertEqual(dados['nome'], 'PET SHOP AMIGO FIEL')
        self.assertEqual(dados['mapa']['registro'], 'SP0001')
        self.assertTrue(dados['mapa']['ativo'])
        self.assertEqual(dados['numero'], '1000')
        self.assertEqual(dados['complemento'], 'LOJA 2')
        self.assertEqual(dados['logradouro'], 'Avenida Paulista')
        self.assertEqual(dados['cidade'], 'São Paulo')
        self.assertEqual(dados['tipo_sugerido'], 'petshop')
        self.assertTrue(dados['endereco_completo'])

    def teste_cnpj_sem_registro_no_mapa(self):
        dados = self.consultar(CNPJ_AGRO).json()

        self.assertIsNone(dados['mapa'])
        self.assertEqual(dados['nome'], 'PET SHOP AMIGO FIEL')  # vem da Receita

    def teste_receita_fora_do_ar_usa_o_que_o_mapa_sabe(self):
        dados = self.consultar(CNPJ_PET, receita=URLError('fora do ar')).json()

        self.assertEqual(dados['nome'], 'PET SHOP AMIGO FIEL')
        self.assertEqual(dados['cidade'], 'São Paulo')
        self.assertFalse(dados['endereco_completo'])

    def teste_erros(self):
        self.assertEqual(self.consultar('12345678000100').status_code, 400)
        self.assertEqual(self.consultar(CNPJ_AGRO, receita=URLError('fora')).status_code, 503)
        resposta = self.consultar(CNPJ_AGRO, receita=HTTPError('u', 404, 'x', {}, None))
        self.assertEqual(resposta.status_code, 404)

    def teste_avisa_quando_o_cnpj_ja_esta_cadastrado(self):
        farmacia = Farmacia.objects.create(nome='Pet', endereco='E', cnpj=CNPJ_PET)
        self.assertTrue(self.consultar(CNPJ_PET).json()['ja_cadastrado'])
        # Na edição do próprio estabelecimento, não é "já cadastrado"
        with patch('farmacia.cnpj._buscar', return_value=RECEITA_PET), \
                patch('farmacia.cep.urlopen', return_value=resposta_json(VIACEP_PAULISTA_LOJA)):
            resposta = self.client.get(
                reverse('farmacia:buscar_cnpj', args=[CNPJ_PET]), {'ignorar': farmacia.id})
        self.assertFalse(resposta.json()['ja_cadastrado'])

    def teste_exige_login(self):
        self.client.logout()
        self.assertEqual(self.consultar(CNPJ_PET).status_code, 302)


class SugestoesEstabelecimentosTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')
        EstabelecimentoMapa.objects.bulk_create([
            EstabelecimentoMapa(cnpj=CNPJ_PET, razao_social='PET AMIGO LTDA',
                                nome_fantasia='PET SHOP AMIGO FIEL', municipio='Campinas',
                                uf='SP', situacao='ativo', atividades='COMERCIANTE'),
            EstabelecimentoMapa(cnpj=CNPJ_AGRO, razao_social='AGROPECUARIA CAMPO SUL',
                                municipio='Canguçu', uf='RS', situacao='ativo',
                                atividades='COMERCIANTE'),
            EstabelecimentoMapa(cnpj=gerar_cnpj('111111110001'), razao_social='FABRICA VET',
                                municipio='Campinas', uf='SP', situacao='ativo',
                                atividades='FABRICANTE'),
            EstabelecimentoMapa(cnpj=gerar_cnpj('222222220001'), razao_social='PET SHOP FECHADO',
                                municipio='Campinas', uf='SP', situacao='cancelado',
                                atividades='COMERCIANTE'),
        ])

    def sugerir(self, q):
        return self.client.get(reverse('farmacia:sugestoes'), {'q': q}).json()['sugestoes']

    def teste_busca_por_nome_com_erro_de_digitacao(self):
        [primeiro, *_] = self.sugerir('pet shop amigo fiu')
        self.assertEqual(primeiro['nome'], 'PET SHOP AMIGO FIEL')
        self.assertEqual(primeiro['municipio'], 'Campinas')

    def teste_busca_pela_cidade(self):
        nomes = [s['nome'] for s in self.sugerir('agropecuaria cangucu')]
        self.assertEqual(nomes[0], 'AGROPECUARIA CAMPO SUL')

    def teste_busca_pelo_comeco_do_cnpj(self):
        [sugestao] = self.sugerir(CNPJ_AGRO[:8])
        self.assertEqual(sugestao['cnpj'], CNPJ_AGRO)

    def teste_so_sugere_quem_vende_ao_publico_e_esta_ativo(self):
        nomes = [s['nome'] for s in self.sugerir('fabrica vet')] + \
                [s['nome'] for s in self.sugerir('pet shop fechado')]
        self.assertNotIn('FABRICA VET', nomes)
        self.assertNotIn('PET SHOP FECHADO', nomes)

    def teste_indica_ja_cadastrado(self):
        Farmacia.objects.create(nome='Pet', endereco='E', cnpj=CNPJ_PET)
        self.assertTrue(self.sugerir('pet shop amigo')[0]['ja_cadastrado'])


class CadastroComCnpjTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')

    def cadastrar(self, **alteracoes):
        return self.client.post(reverse('farmacia:cadastrar'), dados_formulario(**alteracoes))

    def teste_salva_o_cnpj_so_com_os_digitos(self):
        self.cadastrar(cnpj=modulo_cnpj.formatar_cnpj(CNPJ_PET))
        self.assertEqual(Farmacia.objects.get().cnpj, CNPJ_PET)

    def teste_cnpj_invalido_e_recusado(self):
        response = self.cadastrar(cnpj='12.345.678/0001-00')
        self.assertContains(response, 'CNPJ inválido')
        self.assertFalse(Farmacia.objects.exists())

    def teste_cnpj_nao_pode_repetir(self):
        self.cadastrar(cnpj=CNPJ_PET, numero='1')
        response = self.cadastrar(cnpj=CNPJ_PET, numero='2')

        self.assertContains(response, 'Já existe um estabelecimento cadastrado com o CNPJ')
        self.assertEqual(Farmacia.objects.count(), 1)

    def teste_varios_estabelecimentos_sem_cnpj(self):
        self.cadastrar(numero='1')
        self.cadastrar(numero='2')
        self.assertEqual(Farmacia.objects.count(), 2)

    def teste_selo_registrado_no_mapa_na_lista(self):
        """Selo aparece só para CNPJ com registro ATIVO no MAPA"""
        EstabelecimentoMapa.objects.create(
            cnpj=CNPJ_PET, razao_social='PET', situacao='ativo', atividades='COMERCIANTE')
        EstabelecimentoMapa.objects.create(
            cnpj=CNPJ_AGRO, razao_social='AGRO', situacao='cancelado', atividades='COMERCIANTE')
        self.cadastrar(nome_farmacia='Registrado', cnpj=CNPJ_PET)
        self.cadastrar(nome_farmacia='Cancelado', cnpj=CNPJ_AGRO)
        self.cadastrar(nome_farmacia='Sem CNPJ', numero='3')

        response = self.client.get(reverse('farmacia:listar'))
        self.assertContains(response, 'Registrado no MAPA', count=1)
        self.assertContains(response, 'CNPJ ' + modulo_cnpj.formatar_cnpj(CNPJ_PET))
