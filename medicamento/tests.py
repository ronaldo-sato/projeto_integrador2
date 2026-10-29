from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from django.contrib.auth.models import User

from .models import Medicamento

# Testes de proteção das views (login obrigatório)


class MedicamentoLoginObrigatorioTests(TestCase):

    def setUp(self):
        self.username = "usuario_teste"
        self.password = "senha_segura123"
        User.objects.create_user(
            username=self.username, password=self.password)

        self.medicamento = Medicamento.objects.create(
            nome='Dipirona', fabricante='Fabricante Teste')

        self.url_cadastrar = reverse('medicamento:cadastrar')
        self.url_listar = reverse('medicamento:listar')
        self.url_atualizar = reverse(
            'medicamento:atualizar', args=[self.medicamento.id])
        self.url_deletar = reverse(
            'medicamento:deletar', args=[self.medicamento.id])

    def url_login(self, url):
        """URL para onde o visitante é enviado ao acessar uma view
        protegida"""
        return f"{reverse('base:index')}?next={url}"

    def teste_visitante_nao_cadastra_medicamento(self):
        """Garantir que sem login não é possível cadastrar"""
        response = self.client.post(self.url_cadastrar, {
            'nome_medicamento': 'Remédio Intruso',
            'fabricante': 'Fabricante Intruso'})

        self.assertRedirects(response, self.url_login(self.url_cadastrar))
        self.assertFalse(
            Medicamento.objects.filter(nome='Remédio Intruso').exists())

    def teste_visitante_nao_lista_medicamentos(self):
        """Garantir que sem login a listagem não é exibida"""
        response = self.client.get(self.url_listar)

        self.assertRedirects(response, self.url_login(self.url_listar))

    def teste_visitante_nao_atualiza_medicamento(self):
        """Garantir que sem login não é possível editar"""
        response = self.client.post(self.url_atualizar, {
            'nome_medicamento': 'Nome Alterado',
            'fabricante': 'Fabricante Alterado'})

        self.assertRedirects(response, self.url_login(self.url_atualizar))
        self.medicamento.refresh_from_db()
        self.assertEqual(self.medicamento.nome, 'Dipirona')

    def teste_visitante_nao_deleta_medicamento(self):
        """Garantir que sem login não é possível excluir"""
        response = self.client.post(self.url_deletar)

        self.assertRedirects(response, self.url_login(self.url_deletar))
        self.assertTrue(
            Medicamento.objects.filter(id=self.medicamento.id).exists())

    def teste_usuario_logado_cadastra_medicamento(self):
        """Garantir que com login o cadastro continua funcionando"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, {
            'nome_medicamento': 'Paracetamol',
            'fabricante': 'Fabricante Novo'})

        # Volta para a página de medicamentos, onde aparece o novo registro
        self.assertRedirects(response, self.url_listar)
        self.assertTrue(
            Medicamento.objects.filter(nome='Paracetamol').exists())

    def teste_usuario_logado_deleta_medicamento(self):
        """Garantir que com login a exclusão continua funcionando"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_deletar)

        self.assertRedirects(response, self.url_listar)
        self.assertFalse(
            Medicamento.objects.filter(id=self.medicamento.id).exists())

    def teste_usuario_logado_nao_deleta_por_link(self):
        """Garantir que a exclusão não acontece por GET (um link ou imagem
        de outro site não consegue apagar dados)"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_deletar)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            Medicamento.objects.filter(id=self.medicamento.id).exists())

    def teste_cadastro_com_campo_faltando_nao_quebra(self):
        """Garantir que um envio sem o campo fabricante não gera erro 500"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.url_cadastrar, {'nome_medicamento': 'Sem Fabricante'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preencha o medicamento e o fabricante.')
        self.assertFalse(
            Medicamento.objects.filter(nome='Sem Fabricante').exists())

    def teste_erro_no_cadastro_mantem_secao_e_dados(self):
        """Garantir que após um erro (medicamento repetido) a página de
        medicamentos continua aberta com os dados digitados preenchidos"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, {
            'nome_medicamento': 'Dipirona',
            'fabricante': 'Fabricante Teste'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já está cadastrado!')
        self.assertTemplateUsed(response, 'medicamento/listar.html')
        self.assertContains(response, 'value="Dipirona"')
        self.assertContains(response, 'value="Fabricante Teste"')

    def teste_listagem_nao_executa_script_do_nome(self):
        """Garantir que um nome malicioso não vira código JavaScript no
        botão de confirmação (XSS)"""
        Medicamento.objects.create(
            nome="x');alert('XSS');//", fabricante='Fabricante 2')
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.url_listar)

        corpo = response.content.decode()
        # A página não tem JavaScript embutido no HTML (onclick, onsubmit...):
        # a confirmação usa o atributo data-confirmar, inserido como texto
        self.assertNotRegex(corpo, r'\son[a-z]+\s*=')
        # E o nome aparece escapado (as aspas não "fecham" o atributo)
        self.assertIn('x&#x27;);alert(&#x27;XSS&#x27;);//', corpo)
        self.assertNotIn("x');alert('XSS');//", corpo)

    def teste_nome_maior_que_o_banco_nao_quebra(self):
        """Garantir que um nome maior que o limite do banco (100
        caracteres) mostra erro em vez de gerar erro 500"""
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.url_cadastrar, {
            'nome_medicamento': 'x' * 150, 'fabricante': 'Fabricante Longo'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no máximo 100 caracteres')
        self.assertFalse(
            Medicamento.objects.filter(fabricante='Fabricante Longo').exists())


# ---------------------------------------------------------------------------
# Catálogo do MAPA, busca aproximada (KNN) e sugestões
# ---------------------------------------------------------------------------

import io
import zipfile
from unittest.mock import patch
from xml.sax.saxutils import escape

from django.core.management import call_command

from . import mapa, sugestoes
from .busca import IndiceKNN, levenshtein, trigramas
from .models import ProdutoMapa


def gerar_xlsx(abas, compartilhar_textos=False):
    """Gera um .xlsx mínimo em memória: abas = [(nome, [linhas])]"""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    ns_rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    textos = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as arquivo:
        folhas = ''.join(f'<sheet name="{escape(nome)}" sheetId="{i}" r:id="rId{i}"/>'
                         for i, (nome, _) in enumerate(abas, start=1))
        arquivo.writestr('xl/workbook.xml',
                         f'<workbook xmlns="{ns}" xmlns:r="{ns_rel}"><sheets>{folhas}</sheets></workbook>')
        relacoes = ''.join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>'
                           for i in range(1, len(abas) + 1))
        arquivo.writestr('xl/_rels/workbook.xml.rels', f'<Relationships>{relacoes}</Relationships>')
        for i, (_, linhas) in enumerate(abas, start=1):
            xml_linhas = []
            for n, linha in enumerate(linhas, start=1):
                celulas = []
                for c, valor in enumerate(linha):
                    ref = f'{chr(65 + c)}{n}'
                    if compartilhar_textos:
                        textos.append(valor)
                        celulas.append(f'<c r="{ref}" t="s"><v>{len(textos) - 1}</v></c>')
                    else:
                        celulas.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(valor)}</t></is></c>')
                xml_linhas.append(f'<row r="{n}">{"".join(celulas)}</row>')
            arquivo.writestr(f'xl/worksheets/sheet{i}.xml',
                             f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml_linhas)}</sheetData></worksheet>')
        if compartilhar_textos:
            itens = ''.join(f'<si><t>{escape(t)}</t></si>' for t in textos)
            arquivo.writestr('xl/sharedStrings.xml', f'<sst xmlns="{ns}">{itens}</sst>')
    return buffer.getvalue()


def gerar_ods(abas):
    """Gera um .ods mínimo em memória: abas = [(nome, [linhas])]"""
    tabelas = ''
    for nome, linhas in abas:
        xml_linhas = ''.join(
            '<table:table-row>' + ''.join(
                f'<table:table-cell><text:p>{escape(v)}</text:p></table:table-cell>' for v in linha)
            + '<table:table-cell table:number-columns-repeated="3"/></table:table-row>'
            for linha in linhas)
        tabelas += f'<table:table table:name="{escape(nome)}">{xml_linhas}</table:table>'
    conteudo = (
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        f'<office:body><office:spreadsheet>{tabelas}</office:spreadsheet></office:body>'
        '</office:document-content>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as arquivo:
        arquivo.writestr('content.xml', conteudo)
    return buffer.getvalue()


TITULO = ['Ministério da Agricultura e Pecuária']
CABECALHO_TRIMESTRAL = ['Nº', 'Estabelecimento', 'Natureza da Solicitação',
                        'Situação da solicitação', 'Produto']


class LeituraPlanilhasTests(TestCase):

    def teste_le_xlsx_com_textos_compartilhados_e_em_linha(self):
        """Garantir que os dois jeitos de guardar texto no .xlsx são lidos"""
        abas = [('Aba 1', [['Produto', 'Empresa'], ['BRAVECTO', 'MSD']])]
        for compartilhar in (False, True):
            self.assertEqual(
                mapa.ler_planilha(gerar_xlsx(abas, compartilhar)),
                [('Aba 1', [['Produto', 'Empresa'], ['BRAVECTO', 'MSD']])])

    def teste_le_ods(self):
        """Garantir que planilhas do LibreOffice (.ods) também são lidas e as
        células vazias repetidas no fim da linha são descartadas"""
        abas = mapa.ler_planilha(gerar_ods([('DEFERIDO', [['Produto'], ['APOQUEL']])]))
        self.assertEqual(abas, [('DEFERIDO', [['Produto'], ['APOQUEL']])])

    def teste_conteudo_que_nao_e_planilha(self):
        """Garantir que links que são páginas HTML são ignorados"""
        self.assertEqual(mapa.ler_planilha(b'<html>pagina</html>'), [])


class InterpretacaoPlanilhasTests(TestCase):

    def eventos(self, aba, linhas, origem='planilha-farmaceuticos.xlsx'):
        return mapa.extrair_eventos([(aba, linhas)], origem=origem)

    def teste_lista_de_registrados_de_2019(self):
        """Garantir a leitura da lista do PUBLIVET, com as informações extras"""
        linhas = [
            ['LISTA DE PRODUTOS REGISTRADOS'],
            ['Nome do estabelecimento', 'Nome do produto', 'Natureza do produto',
             'Número da última licença', 'É destinado a animais de produção?',
             'Sujeito a controle especial (IN 35/2017)'],
            ['BAYER S/A', 'VERAFLOX SUSPENSÃO', 'Farmacêutico - Não Homeopático',
             '000163-0.000005', 'Não', 'Não'],
        ]
        [evento] = self.eventos('3- Produtos Registrados-MAPA', linhas,
                                origem='lista_produtos_registrados.xlsx')

        self.assertEqual(evento.nome, 'VERAFLOX SUSPENSÃO')
        self.assertEqual(evento.empresa, 'BAYER S/A')
        self.assertEqual(evento.situacao, mapa.REGISTRADO)
        self.assertEqual(evento.natureza, 'farmaceutico')
        self.assertEqual(evento.registro, '000163-0.000005')
        self.assertIs(evento.animais_producao, False)
        self.assertIs(evento.controle_especial, False)

    def teste_planilha_trimestral(self):
        """Garantir: deferido entra, indeferido e consulta técnica não,
        cancelamento é registrado como cancelado"""
        linhas = [TITULO, TITULO, CABECALHO_TRIMESTRAL,
                  ['1', 'VETNIL', 'REGISTRO DE PRODUTO', 'DEFERIDA', 'TORSEMIDA COMPRIMIDO'],
                  ['2', 'OUROFINO', 'REGISTRO DE PRODUTO', 'INDEFERIDA', 'PRODUTO NEGADO'],
                  ['3', 'ZOETIS', 'CANCELAMENTO DE LICENÇA', 'DEFERIDA', 'SPIROVAC'],
                  ['4', 'HYGIENA', 'CONSULTA TÉCNICA', 'DEFERIDA', 'KIT ELISA'],
                  ['5', 'MSD', 'ALTERAÇÃO DE REGISTRO', 'CANCELADA', 'PRODUTO ANTIGO']]
        eventos = {e.nome: e.situacao for e in self.eventos('DEFERIDO', linhas)}

        self.assertEqual(eventos, {
            'TORSEMIDA COMPRIMIDO': mapa.REGISTRADO,
            'SPIROVAC': mapa.CANCELADO,
            'PRODUTO ANTIGO': mapa.CANCELADO})

    def teste_situacao_pelo_nome_da_aba(self):
        """Garantir que, sem coluna de situação, vale o nome da aba"""
        linhas = [['Razão social', 'Nome do produto'], ['CEVA', 'VACINA X']]

        self.assertEqual(len(self.eventos('Deferidas', linhas)), 1)
        self.assertEqual(self.eventos('Indeferidas', linhas), [])
        self.assertEqual(self.eventos('Concluídos', linhas), [])

    def teste_licenca_provisoria_e_natureza_pelo_arquivo(self):
        """Garantir que o nome do arquivo indica licença provisória e
        natureza biológica"""
        linhas = [['Razão social', 'Nome do produto'], ['CEVA', 'VACINA X']]
        [provisoria] = self.eventos('Deferidas', linhas,
                                    origem='licencas-provisorias-deferidas.xlsx')
        [biologico] = self.eventos('Deferidas', linhas,
                                   origem='produtos-de-natureza-biologica.xlsx')

        self.assertEqual(provisoria.situacao, mapa.LICENCA_PROVISORIA)
        self.assertEqual(biologico.natureza, 'biologico')

    def teste_empresa_numerica_fica_em_branco(self):
        """Garantir que CNPJ/nº de processo digitado na coluna da empresa
        (erro existente nas planilhas oficiais) não vira nome de empresa"""
        linhas = [['Razão social', 'Nome do produto'], ['93.752.442/0001-75', 'ENROMIC']]
        [evento] = self.eventos('Deferidas', linhas)

        self.assertEqual(evento.empresa, '')

    def teste_chave_da_empresa_ignora_variacoes_da_razao_social(self):
        self.assertEqual(
            mapa.chave_empresa('ZOETIS INDÚSTRIA DE PRODUTOS VETERINÁRIOS LTDA'),
            mapa.chave_empresa('Zoetis Industria de Produtos Veterinarios Ltda.'))

    def teste_descobre_planilhas_e_ordena_por_periodo(self):
        """Garantir que só as planilhas de aprovações/registrados são usadas
        e que ficam em ordem cronológica"""
        html = ''.join(f'<a href="https://gov.br/x/listas/{nome}">' for nome in [
            '2026/deferidos-01-02-2026-a-04-05-2026.xlsx',
            'lista_produtos_registrados_2019.xlsx',
            '2026/fila-de-produtos-aguardando-analise.xlsx',
            '2024/deferidos-ano-2024.xlsx'])
        links = sorted(mapa.descobrir_planilhas(html), key=mapa.chave_cronologica)

        self.assertEqual([link.rsplit('/', 1)[-1] for link in links], [
            'lista_produtos_registrados_2019.xlsx', 'deferidos-ano-2024.xlsx',
            'deferidos-01-02-2026-a-04-05-2026.xlsx'])


class BuscaKNNTests(TestCase):

    def setUp(self):
        self.nomes = ['BRAVECTO 20-40 KG', 'BRAVECTO TRANSDERMAL', 'BRAVECILIN',
                      'SIMPARIC 40MG', 'DRONTAL PLUS CÃES', 'APOQUEL 16MG',
                      'VACINA ANTIRRÁBICA LABOVET', 'IVERMECTINA 1%']
        self.indice = IndiceKNN(list(enumerate(self.nomes)))

    def melhor(self, consulta):
        resultado = self.indice.vizinhos(consulta, k=1)
        return self.nomes[resultado[0][0]] if resultado else None

    def teste_trigramas_por_palavra(self):
        self.assertEqual(trigramas('Cão'), [' ca', 'cao', 'ao '])
        self.assertIn(' 40', trigramas('Simparic 40'))

    def teste_distancia_de_edicao(self):
        self.assertEqual(levenshtein('bravekto', 'bravecto'), 1)
        self.assertEqual(levenshtein('', 'abc'), 3)
        self.assertEqual(levenshtein('apoquel', 'apoquel'), 0)

    def teste_encontra_com_erro_de_digitacao(self):
        """O caso que mais importa: o usuário não sabe escrever o nome"""
        self.assertEqual(self.melhor('bravekto')[:8], 'BRAVECTO')
        self.assertEqual(self.melhor('simparik'), 'SIMPARIC 40MG')
        self.assertEqual(self.melhor('apokel'), 'APOQUEL 16MG')

    def teste_reordenacao_corrige_erro_de_digitacao(self):
        """Caso real do catálogo do MAPA: vários produtos 'BRAVET' deixam os
        trigramas 'bra/rav/ave' comuns, e só os trigramas colocariam BRAVET
        PLUS à frente de um BRAVECTO. A distância de edição ('bravekto' está
        a 1 letra de 'bravecto') coloca os dois BRAVECTO nas primeiras
        posições"""
        nomes = ['BRAVECTO 365', 'BRAVECTO TRANSDERMAL', 'BRAVECILIN',
                 'FERRO BRAVET', 'BRAVET PLUS', 'SIMPARIC 40MG']
        indice = IndiceKNN(list(enumerate(nomes)))
        dois_primeiros = [nomes[i] for i, _ in indice.vizinhos('bravekto', k=2)]

        self.assertEqual(sorted(dois_primeiros),
                         ['BRAVECTO 365', 'BRAVECTO TRANSDERMAL'])

    def teste_encontra_nome_incompleto(self):
        self.assertEqual(self.melhor('iverm'), 'IVERMECTINA 1%')

    def teste_ignora_acentos_maiusculas_e_ordem_das_palavras(self):
        self.assertEqual(self.melhor('antirrabica'), 'VACINA ANTIRRÁBICA LABOVET')
        self.assertEqual(self.melhor('caes drontal'), 'DRONTAL PLUS CÃES')

    def teste_sem_semelhanca_nao_sugere(self):
        self.assertIsNone(self.melhor('xyzw'))
        self.assertEqual(self.indice.vizinhos(''), [])

    def teste_k_limita_e_ordena_por_semelhanca(self):
        resultado = self.indice.vizinhos('bravecto', k=2)
        self.assertEqual(len(resultado), 2)
        self.assertGreaterEqual(resultado[0][1], resultado[1][1])


def pagina_listas(*arquivos):
    return ''.join(f'<a href="https://www.gov.br/x/listas/{a}">' for a in arquivos).encode()


class ImportacaoComandoTests(TestCase):

    def importar(self, downloads):
        """Roda o comando com o site do MAPA simulado (sem internet)"""
        def baixar(url):
            if url == mapa.PAGINA_LISTAS:
                return pagina_listas(*[nome for nome in downloads])
            return downloads[url.split('/listas/')[-1].replace('/@@download/file', '')]
        with patch('medicamento.mapa.baixar', side_effect=baixar):
            call_command('importar_produtos_mapa', stdout=io.StringIO(), stderr=io.StringIO())

    def teste_importa_e_respeita_a_ordem_cronologica(self):
        """Registrado em 2019, cancelado em 2025: fica cancelado. Cancelado
        em 2024 e registrado de novo em 2026: volta a valer"""
        lista_2019 = gerar_xlsx([('3- Produtos Registrados-MAPA', [
            ['Nome do estabelecimento', 'Nome do produto', 'É destinado a animais de produção?'],
            ['ZOETIS', 'SPIROVAC', 'Sim'],
            ['MSD', 'BRAVECTO', 'Não']])])
        cancela_2024 = gerar_ods([('DEFERIDO', [CABECALHO_TRIMESTRAL,
                                  ['1', 'MSD', 'CANCELAMENTO DE REGISTRO', 'DEFERIDA', 'BRAVECTO']])])
        cancela_2025 = gerar_xlsx([('DEFERIDO', [CABECALHO_TRIMESTRAL,
                                   ['1', 'Zoetis Ltda.', 'CANCELAMENTO DE LICENÇA', 'DEFERIDA', 'SPIROVAC']])])
        registra_2026 = gerar_xlsx([('DEFERIDO', [CABECALHO_TRIMESTRAL,
                                    ['1', 'MSD', 'REGISTRO DE PRODUTO', 'DEFERIDA', 'BRAVECTO'],
                                    ['2', 'VETNIL', 'REGISTRO DE PRODUTO', 'DEFERIDA', 'TORSEMIDA']])])

        # Fora de ordem de propósito: o comando ordena pelo período
        self.importar({
            'deferidos-01-02-2026-a-04-05-2026.xlsx': registra_2026,
            'lista_produtos_registrados_2019.xlsx': lista_2019,
            'deferidos-01-01-2025-a-31-03-2025.xlsx': cancela_2025,
            'deferidos-ano-2024.ods': cancela_2024,
        })

        situacao = dict(ProdutoMapa.objects.values_list('nome', 'situacao'))
        self.assertEqual(situacao, {'SPIROVAC': 'cancelado', 'BRAVECTO': 'registrado',
                                    'TORSEMIDA': 'registrado'})
        # A informação extra da lista de 2019 é mantida após novos eventos
        self.assertIs(ProdutoMapa.objects.get(nome='BRAVECTO').animais_producao, False)

    def teste_reimportar_substitui_o_catalogo(self):
        planilha = gerar_xlsx([('DEFERIDO', [CABECALHO_TRIMESTRAL,
                               ['1', 'VETNIL', 'REGISTRO DE PRODUTO', 'DEFERIDA', 'TORSEMIDA']])])
        self.importar({'deferidos-2025.xlsx': planilha})
        self.importar({'deferidos-2025.xlsx': planilha})

        self.assertEqual(ProdutoMapa.objects.count(), 1)


class SugestoesTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')
        self.url = reverse('medicamento:sugestoes')
        ProdutoMapa.objects.bulk_create([
            ProdutoMapa(chave='1', nome='BRAVECTO TRANSDERMAL', empresa='MERCK SHARP & DOHME',
                        situacao='registrado', natureza='farmaceutico'),
            ProdutoMapa(chave='2', nome='BRAVECTO ANTIGO', empresa='MSD', situacao='cancelado'),
            ProdutoMapa(chave='3', nome='SIMPARIC', empresa='ZOETIS', situacao='licenca_provisoria'),
        ])
        Medicamento.objects.create(nome='Bravecto 20-40 kg', fabricante='MSD')

    def sugerir(self, q):
        return self.client.get(self.url, {'q': q}).json()['sugestoes']

    def teste_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {'q': 'brav'}).status_code, 302)

    def teste_sugere_cadastrados_primeiro_e_depois_o_mapa(self):
        resultado = self.sugerir('bravekto')

        self.assertEqual(resultado[0]['fonte'], 'cadastrado')
        self.assertEqual(resultado[0]['nome'], 'Bravecto 20-40 kg')
        mapa_item = next(r for r in resultado if r['fonte'] == 'mapa')
        self.assertEqual(mapa_item['nome'], 'BRAVECTO TRANSDERMAL')
        self.assertEqual(mapa_item['fabricante'], 'MERCK SHARP & DOHME')
        self.assertEqual(mapa_item['natureza'], 'Farmacêutico')

    def teste_marcas_do_mesmo_medicamento_viram_uma_sugestao(self):
        """Garantir que o mesmo nome cadastrado com várias marcas aparece
        uma vez só, listando as marcas"""
        Medicamento.objects.create(nome='Bravecto 20-40 kg', fabricante='Genérico')
        cadastrados = [r for r in self.sugerir('bravecto') if r['fonte'] == 'cadastrado']

        self.assertEqual(len(cadastrados), 1)
        self.assertEqual(cadastrados[0]['fabricante'], 'Genérico, MSD')

    def teste_produto_cancelado_nao_e_sugerido(self):
        nomes = [r['nome'] for r in self.sugerir('bravecto')]
        self.assertNotIn('BRAVECTO ANTIGO', nomes)

    def teste_indica_licenca_provisoria(self):
        [simparic] = self.sugerir('simparik')
        self.assertTrue(simparic['licenca_provisoria'])

    def teste_consulta_curta_nao_busca(self):
        self.assertEqual(self.sugerir('b'), [])

    def teste_catalogo_reimportado_atualiza_as_sugestoes(self):
        """Garantir que o índice em memória é refeito após uma importação"""
        self.assertEqual(self.sugerir('nexgard'), [])
        ProdutoMapa.objects.create(chave='4', nome='NEXGARD', empresa='BOEHRINGER',
                                   situacao='registrado')
        self.assertEqual(self.sugerir('nexgard')[0]['nome'], 'NEXGARD')

    def teste_nome_longo_e_ajustado_ao_campo_do_cadastro(self):
        """Nomes do MAPA com mais de 100 caracteres ficam só com o nome
        comercial (antes do ' - '), que cabe no campo do cadastro"""
        longo = 'PEST VAC - ' + 'Vacina viva modificada contra a Peste Suína Clássica ' * 3
        self.assertEqual(sugestoes.encurtar(longo, 100), 'PEST VAC')
        self.assertLessEqual(len(sugestoes.encurtar('palavra ' * 30, 100)), 100)

    def teste_pagina_tem_o_campo_de_autocompletar(self):
        response = self.client.get(reverse('medicamento:listar'))
        self.assertContains(response, 'role="combobox"')
        self.assertContains(response, 'data-url-sugestoes="/medicamento/sugestoes/"')


# Ilustração dos medicamentos pela forma (comprimido, injetável...)

from pathlib import Path

from django.conf import settings

from .formas import FORMAS, identificar_forma, ilustrar


class FormasTests(TestCase):

    def teste_identifica_a_forma_pelo_nome(self):
        exemplos = {
            'Ivomec Injetável': 'injetavel',
            'VETMEDIN COMPRIMIDOS MASTIGÁVEIS': 'comprimido',
            'Ciclorvet Pour-On': 'pipeta',
            'PROFENDER SPOTON': 'pipeta',
            'BRAVECTO TRANSDERMAL': 'pipeta',
            'Shampoo Bulldog Antipulgas': 'shampoo',
            'TIURAN AEROSSOL': 'spray',
            'Coleira Antipulgas': 'coleira',
            'POMADA SARALOGO': 'pomada',
            'Colírio Biofarm': 'gotas',
            'FENCARE 4% PREMIX': 'po',
            'Dufulvin Suspensão Oral': 'liquido',
            'Omeprazol Cápsulas': 'capsula',
            'NOBIVAC RAIVA': 'vacina',
            'Vacina contra Raiva': 'vacina',
            'ACCUVET PARVO AG TEST': 'diagnostico',
            'IMUNOTESTE EHRLICHIA': 'diagnostico',
        }
        for nome, chave in exemplos.items():
            with self.subTest(nome=nome):
                self.assertEqual(identificar_forma(nome).chave, chave)

    def teste_regra_mais_especifica_vence(self):
        """'Solução injetável' é injetável (não líquido oral); kit de
        diagnóstico de vacina é teste (não vacina)... e palavras que só
        contêm o termo não contam"""
        self.assertEqual(identificar_forma('Ivermectina Solução Injetável').chave, 'injetavel')
        self.assertEqual(identificar_forma('Testosterona Gel').chave, 'pomada')
        self.assertEqual(identificar_forma('Pomposo').chave, 'medicamento')

    def teste_nome_sem_forma_usa_desenho_generico(self):
        forma = identificar_forma('Bravecto')
        self.assertEqual((forma.chave, forma.rotulo), ('medicamento', 'Medicamento'))

    def teste_biologico_do_mapa_sem_forma_no_nome_vira_vacina(self):
        self.assertEqual(identificar_forma('Recombitek C8', biologico=True).chave, 'vacina')
        # O nome continua tendo prioridade
        self.assertEqual(identificar_forma('Kit Elisa', biologico=True).chave, 'diagnostico')

    def teste_ilustrar_consulta_o_catalogo_uma_vez_para_a_lista(self):
        ProdutoMapa.objects.create(chave='1', nome='RECOMBITEK C8', situacao='registrado',
                                   natureza='biologico')
        medicamentos = [Medicamento(nome='Recombitek C8', fabricante='A'),
                        Medicamento(nome='Bravecto', fabricante='B'),
                        Medicamento(nome='Ivomec Injetável', fabricante='C')]
        with self.assertNumQueries(1):
            ilustrar(medicamentos)
        self.assertEqual([m.forma.chave for m in medicamentos],
                         ['vacina', 'medicamento', 'injetavel'])

    def teste_toda_forma_tem_desenho_e_cor(self):
        sprite = (Path(__file__).parent / 'templates/medicamento/partials/sprite_formas.html').read_text('utf-8')
        css = (Path(settings.BASE_DIR) / 'base_static/global/css/app.css').read_text('utf-8')
        for forma in FORMAS:
            with self.subTest(forma=forma.chave):
                self.assertIn(f'id="forma-{forma.chave}"', sprite)
                self.assertIn(f'.ilustracao-{forma.chave} ', css)


class IlustracaoNasPaginasTests(TestCase):

    def setUp(self):
        User.objects.create_user(username='u', password='senha_segura123')
        self.client.login(username='u', password='senha_segura123')
        Medicamento.objects.create(nome='Ivomec Injetável', fabricante='Boehringer')

    def teste_lista_de_medicamentos_mostra_desenho_e_forma(self):
        response = self.client.get(reverse('medicamento:listar'))
        self.assertContains(response, 'id="forma-injetavel"')       # desenho na página
        self.assertContains(response, 'ilustracao ilustracao-injetavel')
        self.assertContains(response, '<div class="small text-body-secondary">Injetável</div>', html=True)

    def teste_desenhos_so_para_quem_esta_logado(self):
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('base:index')), 'id="forma-')

    def teste_sugestoes_trazem_a_forma_pelo_nome_completo_do_mapa(self):
        ProdutoMapa.objects.create(
            chave='1', nome='SUISHIELD - ' + 'Vacina viva contra a Peste Suína Clássica ' * 3,
            empresa='X', situacao='registrado')
        [sugestao] = [s for s in self.client.get(
            reverse('medicamento:sugestoes'), {'q': 'suishield'}).json()['sugestoes']
            if s['fonte'] == 'mapa']
        self.assertEqual(sugestao['nome'], 'SUISHIELD')  # nome encurtado...
        self.assertEqual(sugestao['forma'], 'vacina')     # ...forma pelo completo
        self.assertEqual(sugestao['forma_rotulo'], 'Vacina')
