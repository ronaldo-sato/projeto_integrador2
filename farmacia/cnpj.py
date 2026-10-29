"""CNPJ: validação e consulta dos dados públicos da Receita Federal.

A consulta usa a BrasilAPI (https://brasilapi.com.br) e, se ela estiver fora
do ar, a Minha Receita (https://minhareceita.org) como reserva. As duas são
gratuitas, não exigem cadastro e publicam os dados abertos da Receita.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.cache import cache

TEMPO_LIMITE = 8
TEMPO_CACHE = 60 * 60 * 24  # 1 dia
APIS = [
    'https://brasilapi.com.br/api/cnpj/v1/{cnpj}',
    'https://minhareceita.org/{cnpj}',
]


class CnpjInvalido(ValueError):
    """Não tem 14 dígitos ou os dígitos verificadores não conferem."""


class CnpjNaoEncontrado(LookupError):
    """CNPJ válido, mas não encontrado na Receita."""


class ServicoCnpjIndisponivel(RuntimeError):
    """Nenhuma das APIs respondeu."""


def limpar_cnpj(texto):
    """Só os 14 dígitos: '49.475.833/0001-06' -> '49475833000106'"""
    return re.sub(r'\D', '', texto or '')


def formatar_cnpj(digitos):
    return f'{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}'


def _digito(base, pesos):
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    return '0' if resto < 2 else str(11 - resto)


def cnpj_valido(texto):
    """Confere os dois dígitos verificadores do CNPJ (regra da Receita)"""
    digitos = limpar_cnpj(texto)
    if len(digitos) != 14 or len(set(digitos)) == 1:  # 00000000000000 etc.
        return False
    primeiro = _digito(digitos[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    segundo = _digito(digitos[:12] + primeiro, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digitos[12:] == primeiro + segundo


def validar_cnpj(texto):
    """Devolve os 14 dígitos ou lança CnpjInvalido"""
    digitos = limpar_cnpj(texto)
    if not cnpj_valido(digitos):
        raise CnpjInvalido('CNPJ inválido. Confira os números digitados.')
    return digitos


def _buscar(url):
    requisicao = Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'ComparadorPrecosVet/1.0 (Projeto Integrador Univesp)',
    })
    with urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
        return json.loads(resposta.read().decode('utf-8'))


def consultar_receita(texto):
    """Dados públicos do CNPJ na Receita Federal:
    {'cnpj', 'razao_social', 'nome_fantasia', 'cep', 'logradouro',
     'numero', 'complemento', 'bairro', 'cidade', 'uf', 'situacao'}

    Lança CnpjInvalido, CnpjNaoEncontrado ou ServicoCnpjIndisponivel."""
    digitos = validar_cnpj(texto)

    chave_cache = f'cnpj:{digitos}'
    dados = cache.get(chave_cache)
    if dados is not None:
        return dados

    for modelo_url in APIS:
        try:
            resposta = _buscar(modelo_url.format(cnpj=digitos))
            break
        except HTTPError as erro:
            # 404: a API respondeu que o CNPJ não existe
            if erro.code == 404:
                raise CnpjNaoEncontrado from erro
            continue
        except (URLError, TimeoutError, ValueError, OSError):
            continue  # esta API falhou: tenta a próxima
    else:
        raise ServicoCnpjIndisponivel('Não foi possível consultar o CNPJ agora.')

    # A Receita separa o tipo ("AVENIDA") do nome do logradouro
    logradouro = ' '.join(filter(None, [
        resposta.get('descricao_tipo_de_logradouro') or '',
        resposta.get('logradouro') or ''])).strip()
    cep = limpar_cnpj(resposta.get('cep') or '')  # só os dígitos
    dados = {
        'cnpj': digitos,
        'razao_social': (resposta.get('razao_social') or '').strip(),
        'nome_fantasia': (resposta.get('nome_fantasia') or '').strip(),
        'cep': f'{cep[:5]}-{cep[5:]}' if len(cep) == 8 else '',
        'logradouro': logradouro,
        'numero': (resposta.get('numero') or '').strip(),
        'complemento': (resposta.get('complemento') or '').strip(),
        'bairro': (resposta.get('bairro') or '').strip(),
        'cidade': (resposta.get('municipio') or '').strip(),
        'uf': (resposta.get('uf') or '').strip().upper(),
        'situacao': (resposta.get('descricao_situacao_cadastral') or '').strip(),
    }
    cache.set(chave_cache, dados, TEMPO_CACHE)
    return dados
