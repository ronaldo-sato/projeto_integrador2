"""Leitura das planilhas oficiais do MAPA com produtos veterinários.

O MAPA (Ministério da Agricultura e Pecuária) não oferece API pública do
SIPEAGRO para consultar produtos. O que ele publica são planilhas na página
"Listas" da Coordenação de Registro de Produtos Veterinários:

- uma lista de produtos registrados, extraída do sistema PUBLIVET em 2019
  (o próprio MAPA avisa que é parcial);
- planilhas trimestrais com as solicitações deferidas (registros, alterações,
  licenças provisórias e cancelamentos) de 2020 em diante.

Este módulo descobre essas planilhas, lê o conteúdo (.xlsx e .ods, usando só
a biblioteca padrão do Python) e transforma cada linha em um "evento" sobre
um produto. O comando importar_produtos_mapa junta os eventos em ordem
cronológica para montar o catálogo.
"""
import io
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.request import Request, urlopen

PAGINA_LISTAS = (
    'https://www.gov.br/agricultura/pt-br/assuntos/insumos-agropecuarios/'
    'insumos-pecuarios/produtos-veterinarios/listas/listas')
TEMPO_LIMITE = 120
CABECALHOS_HTTP = {'User-Agent': 'ComparadorPrecosVet/1.0 (Projeto Integrador Univesp)'}

# Situações de um produto no catálogo
REGISTRADO = 'registrado'
LICENCA_PROVISORIA = 'licenca_provisoria'
CANCELADO = 'cancelado'


@dataclass
class Evento:
    """O que uma linha de planilha diz sobre um produto"""
    nome: str
    empresa: str
    situacao: str               # REGISTRADO, LICENCA_PROVISORIA ou CANCELADO
    natureza: str = ''          # 'farmaceutico', 'biologico' ou ''
    registro: str = ''
    animais_producao: bool | None = None
    controle_especial: bool | None = None


# ---------------------------------------------------------------- textos

def normalizar(texto):
    """Minúsculas, sem acentos e sem pontuação: 'Vacina Antirrábica®' ->
    'vacina antirrabica'. Usado para comparar textos escritos de jeitos
    diferentes"""
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = texto.encode('ascii', 'ignore').decode().lower()
    texto = re.sub(r'[^a-z0-9]+', ' ', texto)
    return texto.strip()


# Sufixos de razão social que não ajudam a identificar a empresa
SUFIXOS_EMPRESA = re.compile(
    r'\b(ltda|s a|sa|s/a|eireli|epp|me|cia|industria|comercio|e|de|do|da|'
    r'dos|das|produtos|veterinarios|veterinaria|brasil)\b')


def chave_empresa(empresa):
    """Identifica a empresa ignorando variações de escrita da razão social
    ('ZOETIS INDÚSTRIA DE PRODUTOS VETERINÁRIOS LTDA' == 'Zoetis Ltda.')"""
    return re.sub(r'\s+', ' ', SUFIXOS_EMPRESA.sub(' ', normalizar(empresa))).strip()


def sim_ou_nao(valor):
    valor = normalizar(valor)
    if valor in ('sim', 's'):
        return True
    if valor in ('nao', 'n'):
        return False
    return None


# ---------------------------------------------------------------- planilhas

NS_XLSX = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_ODS_TABELA = 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
NS_ODS_TEXTO = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'


def _indice_coluna(referencia):
    """'C7' -> 2 (coluna A = 0)"""
    letras = re.match(r'[A-Z]+', referencia or '')
    if not letras:
        return None
    indice = 0
    for letra in letras.group():
        indice = indice * 26 + ord(letra) - ord('A') + 1
    return indice - 1


def ler_xlsx(conteudo):
    """Lê um .xlsx (zip com XML) e devolve [(nome_da_aba, linhas)]"""
    arquivo = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = arquivo.namelist()
    t = f'{{{NS_XLSX}}}'

    compartilhados = []
    if 'xl/sharedStrings.xml' in nomes:
        for si in ET.fromstring(arquivo.read('xl/sharedStrings.xml')).findall(t + 'si'):
            compartilhados.append(''.join(x.text or '' for x in si.iter(t + 't')))

    destinos = {
        rel.get('Id'): rel.get('Target')
        for rel in ET.fromstring(arquivo.read('xl/_rels/workbook.xml.rels'))}

    abas = []
    pasta = ET.fromstring(arquivo.read('xl/workbook.xml'))
    for aba in pasta.find(t + 'sheets'):
        caminho = destinos[aba.get(f'{{{NS_REL}}}id')].lstrip('/')
        if not caminho.startswith('xl/'):
            caminho = 'xl/' + caminho
        linhas = []
        for linha in ET.fromstring(arquivo.read(caminho)).iter(t + 'row'):
            celulas = {}
            for posicao, celula in enumerate(linha.findall(t + 'c')):
                coluna = _indice_coluna(celula.get('r'))
                coluna = posicao if coluna is None else coluna
                valor = celula.find(t + 'v')
                if celula.get('t') == 's' and valor is not None:
                    texto = compartilhados[int(valor.text)]
                elif celula.get('t') == 'inlineStr':
                    texto = ''.join(x.text or '' for x in celula.iter(t + 't'))
                else:
                    texto = valor.text if valor is not None else ''
                celulas[coluna] = (texto or '').strip()
            if celulas:
                linhas.append([celulas.get(i, '') for i in range(max(celulas) + 1)])
        abas.append((aba.get('name'), linhas))
    return abas


def ler_ods(conteudo):
    """Lê um .ods (planilha do LibreOffice) e devolve [(nome_da_aba, linhas)]"""
    tabela = f'{{{NS_ODS_TABELA}}}'
    paragrafo = f'{{{NS_ODS_TEXTO}}}p'
    raiz = ET.fromstring(zipfile.ZipFile(io.BytesIO(conteudo)).read('content.xml'))
    abas = []
    for aba in raiz.iter(tabela + 'table'):
        linhas = []
        for linha in aba.iter(tabela + 'table-row'):
            celulas = []
            for celula in linha.findall(tabela + 'table-cell'):
                texto = ' '.join(''.join(p.itertext()) for p in celula.findall(paragrafo)).strip()
                # Células repetidas (comuns no fim da linha) são compactadas
                repeticoes = min(int(celula.get(tabela + 'number-columns-repeated', '1')), 50)
                celulas.extend([texto] * repeticoes)
            while celulas and not celulas[-1]:
                celulas.pop()
            if celulas:
                linhas.append(celulas)
        abas.append((aba.get(tabela + 'name'), linhas))
    return abas


def ler_planilha(conteudo):
    """Lê .xlsx ou .ods (descobre o formato pelo conteúdo). Devolve [] se
    não for uma planilha (alguns links da página são páginas HTML)"""
    try:
        nomes = zipfile.ZipFile(io.BytesIO(conteudo)).namelist()
    except zipfile.BadZipFile:
        return []
    if 'content.xml' in nomes:
        return ler_ods(conteudo)
    if 'xl/workbook.xml' in nomes:
        return ler_xlsx(conteudo)
    return []


# ---------------------------------------------------------------- linhas

def mapear_colunas(cabecalho):
    """Descobre em qual coluna está cada informação. Os nomes das colunas
    mudam de um ano para outro ('Produto', 'Nome do produto', 'Empresa',
    'Razão social'...)"""
    colunas = {}
    for indice, titulo in enumerate(cabecalho):
        t = normalizar(titulo)
        if not t:
            continue
        if 'produto' not in colunas and (
                t in ('produto', 'nome do produto', 'nome comercial')
                or t.startswith('produto ')):
            colunas['produto'] = indice
        elif 'empresa' not in colunas and re.search(
                r'^(nome do estabelecimento|estabelecimento|empresa|razao social|interessado)$', t):
            colunas['empresa'] = indice
        elif 'situacao' not in colunas and t.startswith('situacao'):
            colunas['situacao'] = indice
        elif 'solicitacao' not in colunas and re.search(
                r'^(natureza da solicitacao|tipo da solicitacao|assunto)$', t):
            colunas['solicitacao'] = indice
        elif 'natureza' not in colunas and t == 'natureza do produto':
            colunas['natureza'] = indice
        elif 'producao' not in colunas and 'animais de producao' in t:
            colunas['producao'] = indice
        elif 'controle' not in colunas and 'controle especial' in t:
            colunas['controle'] = indice
        elif 'registro' not in colunas and re.search(
                r'^(numero da (ultima )?licenca|registro do produto)$', t):
            colunas['registro'] = indice
    return colunas


def natureza_do_produto(texto):
    texto = normalizar(texto)
    if 'biolog' in texto:
        return 'biologico'
    if 'farmac' in texto:
        return 'farmaceutico'
    return ''


def _situacao(aba, colunas, linha, origem):
    """Decide o que a linha significa para o produto, ou None se ela não
    altera o catálogo (indeferido, arquivado, consulta técnica...)"""
    def celula(chave):
        indice = colunas.get(chave)
        return normalizar(linha[indice]) if indice is not None and indice < len(linha) else ''

    resultado = celula('situacao') or normalizar(aba)
    if any(p in resultado for p in ('indefer', 'arquiv', 'pendencia', 'conclu', 'analise')):
        return None

    # Cancelamento pode vir na situação ("CANCELADA") ou no tipo do pedido
    # ("Cancelamento de licença" dentro da aba de deferidos)
    pedido = celula('solicitacao')
    if 'cancel' in resultado or 'cancel' in pedido:
        return CANCELADO
    if 'registrados' not in resultado and 'defer' not in resultado:
        return None
    if 'consulta' in pedido:
        return None
    if 'provis' in pedido or 'provis' in normalizar(origem):
        return LICENCA_PROVISORIA
    return REGISTRADO


def extrair_eventos(abas, origem=''):
    """Transforma as linhas das planilhas em eventos sobre produtos.
    origem: nome/endereço do arquivo (indica natureza e licença provisória)"""
    eventos = []
    natureza_arquivo = natureza_do_produto(origem)
    for aba, linhas in abas:
        # O cabeçalho fica depois de algumas linhas de título do ministério
        inicio = next((i for i, linha in enumerate(linhas[:25])
                       if 'produto' in mapear_colunas(linha)), None)
        if inicio is None:
            continue
        colunas = mapear_colunas(linhas[inicio])
        for linha in linhas[inicio + 1:]:
            def celula(chave):
                indice = colunas.get(chave)
                return linha[indice].strip() if indice is not None and indice < len(linha) else ''

            nome = re.sub(r'\s+', ' ', celula('produto'))
            if len(normalizar(nome)) < 2:
                continue
            situacao = _situacao(aba, colunas, linha, origem)
            if situacao is None:
                continue
            empresa = re.sub(r'\s+', ' ', celula('empresa'))
            # Algumas linhas das planilhas oficiais têm CNPJ ou nº de processo
            # digitado na coluna da empresa: melhor deixar em branco
            if re.match(r'^\d', empresa):
                empresa = ''
            eventos.append(Evento(
                nome=nome,
                empresa=empresa,
                situacao=situacao,
                natureza=natureza_do_produto(celula('natureza')) or natureza_arquivo,
                registro=celula('registro')[:60],
                animais_producao=sim_ou_nao(celula('producao')),
                controle_especial=sim_ou_nao(celula('controle')),
            ))
    return eventos


# ---------------------------------------------------------------- download

def baixar(url):
    requisicao = Request(url, headers=CABECALHOS_HTTP)
    with urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
        return resposta.read()


def descobrir_planilhas(html):
    """Links das planilhas com produtos aprovados (ou a lista de
    registrados) na página de listas do MAPA"""
    links = []
    for link in re.findall(r'href="([^"]+)"', html):
        if '/listas/' not in link or not re.search(r'deferid|registrados', link, re.I):
            continue
        link = link.split('/@@download')[0].rstrip('/')
        if link not in links:
            links.append(link)
    return links


def url_de_download(link):
    return link + '/@@download/file'


def chave_cronologica(link):
    """Data aproximada do período da planilha, para processar em ordem
    (a última data que aparece no nome do arquivo)"""
    datas = re.findall(r'(\d{2})[.-](\d{2})[.-](20\d{2})', link)
    if datas:
        dia, mes, ano = datas[-1]
        return (int(ano), int(mes), int(dia))
    anos = re.findall(r'20\d{2}', link)
    if 'registrados' in link.lower():
        return (2019, 5, 27)  # data da extração do PUBLIVET
    return (int(anos[-1]), 12, 31) if anos else (2000, 1, 1)
