"""Estabelecimentos registrados no MAPA (dados abertos do SIPEAGRO).

O MAPA publica, no portal de dados abertos, o CSV "Produto Veterinário" com
os estabelecimentos registrados para comercializar, fabricar, manipular...
produtos veterinários (atualizado semanalmente). Cada linha é uma combinação
estabelecimento + atividade + classificação, então um mesmo CNPJ aparece em
várias linhas; aqui elas são consolidadas em um registro por CNPJ.
"""
import csv
import io
import json
from urllib.request import Request, urlopen

from medicamento.mapa import normalizar

# API do portal de dados abertos do MAPA (padrão CKAN): devolve a lista de
# arquivos do conjunto de dados, com o endereço atual de cada um
API_CONJUNTO = 'https://dados.agricultura.gov.br/api/3/action/package_show?id=sipeagro'
NOME_RECURSO = 'produto veterinario'
TEMPO_LIMITE = 180
CABECALHOS_HTTP = {'User-Agent': 'ComparadorPrecosVet/1.0 (Projeto Integrador Univesp)'}

# Atividades de quem vende ao público (as outras são fabricante, importador,
# distribuidor, laboratório de controle de qualidade...)
ATIVIDADES_VAREJO = {'COMERCIANTE', 'MANIPULADOR'}


def baixar(url):
    with urlopen(Request(url, headers=CABECALHOS_HTTP), timeout=TEMPO_LIMITE) as resposta:
        return resposta.read()


def url_do_csv():
    """Endereço atual do CSV 'Produto Veterinário' no portal de dados abertos"""
    conjunto = json.loads(baixar(API_CONJUNTO).decode('utf-8'))
    for recurso in conjunto['result']['resources']:
        if normalizar(recurso.get('name')) == NOME_RECURSO:
            return recurso['url']
    raise LookupError('Arquivo "Produto Veterinário" não encontrado no portal do MAPA.')


def _nome_valido(texto):
    """Nome fantasia vazio ou mascarado ('********') não serve"""
    texto = (texto or '').strip()
    return texto if texto.strip('*. -') else ''


def ler_estabelecimentos(conteudo):
    """Lê o CSV e devolve um dicionário por CNPJ (14 dígitos)"""
    texto = conteudo.decode('utf-8-sig')
    estabelecimentos = {}
    for linha in csv.DictReader(io.StringIO(texto), delimiter=';'):
        cnpj = ''.join(c for c in linha.get('CNPJ', '') if c.isdigit())
        if len(cnpj) != 14:
            continue
        e = estabelecimentos.setdefault(cnpj, {
            'cnpj': cnpj,
            'registro': (linha.get('NUMERO_REGISTRO_ESTABELECIMENTO') or '').strip(),
            'razao_social': (linha.get('RAZAO_SOCIAL') or '').strip(),
            'nome_fantasia': _nome_valido(linha.get('NOME_FANTASIA')),
            'municipio': (linha.get('MUNICIPIO') or '').strip(),
            'uf': (linha.get('UNIDADE_DA_FEDERACAO') or '').strip().upper(),
            'situacoes': set(), 'atividades': set(), 'classificacoes': set(),
        })
        e['situacoes'].add(normalizar(linha.get('STATUS_DO_REGISTRO')))
        for campo, coluna in (('atividades', 'ATIVIDADE'), ('classificacoes', 'CLASSIFICACAO')):
            valor = (linha.get(coluna) or '').strip()
            if valor:
                e[campo].add(valor)

    for e in estabelecimentos.values():
        # Uma atividade ativa basta para o registro valer
        situacoes = e.pop('situacoes')
        e['situacao'] = ('ativo' if 'ativo' in situacoes
                         else 'suspenso' if 'suspenso' in situacoes else 'cancelado')
        e['atividades'] = ', '.join(sorted(e['atividades']))[:255]
        e['classificacoes'] = ', '.join(sorted(e['classificacoes']))[:255]
    return estabelecimentos


# Palavras do nome que indicam o tipo de estabelecimento (o usuário confirma)
PISTAS_TIPO = [
    ('clinica', ('clinica', 'hospital', 'consultorio')),
    ('agropecuaria', ('agro', 'agropecuaria', 'cooperativa', 'coop', 'rural', 'campo')),
    ('petshop', ('pet', 'petshop', 'animal', 'bicho', 'cao', 'gato')),
    ('farmacia', ('farma', 'farmacia', 'drogaria', 'manipulacao')),
]


def sugerir_tipo(nome, atividades=''):
    """Tipo provável do estabelecimento, pelo nome e pela atividade no MAPA"""
    palavras = normalizar(nome).split()
    for tipo, pistas in PISTAS_TIPO:
        if any(p.startswith(pista) for p in palavras for pista in pistas):
            return tipo
    if 'MANIPULADOR' in atividades:
        return 'farmacia'
    return ''
