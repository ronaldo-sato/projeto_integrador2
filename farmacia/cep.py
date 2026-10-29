"""Consulta de endereço pelo CEP usando APIs públicas brasileiras.

Usa a ViaCEP (https://viacep.com.br) e, se ela estiver fora do ar, a
BrasilAPI (https://brasilapi.com.br) como reserva. Nenhuma das duas exige
cadastro ou chave de acesso.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.cache import cache

# Tempo máximo de espera por cada API (segundos)
TEMPO_LIMITE = 5
# CEPs consultados ficam guardados por 1 dia (evita repetir a consulta)
TEMPO_CACHE = 60 * 60 * 24


class CepInvalido(ValueError):
    """O texto informado não tem 8 dígitos."""


class CepNaoEncontrado(LookupError):
    """O CEP tem formato válido, mas não existe."""


class ServicoCepIndisponivel(RuntimeError):
    """Nenhuma das APIs respondeu (sem internet ou serviços fora do ar)."""


def limpar_cep(texto):
    """Retorna só os 8 dígitos do CEP (aceita '01310-100' ou '01310100')."""
    digitos = re.sub(r'\D', '', texto or '')
    if len(digitos) != 8:
        raise CepInvalido('O CEP deve ter 8 dígitos.')
    return digitos


def formatar_cep(digitos):
    """'01310100' -> '01310-100'"""
    return f'{digitos[:5]}-{digitos[5:]}'


def _buscar_json(url):
    requisicao = Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'ComparadorPrecosVet/1.0 (Projeto Integrador Univesp)',
    })
    with urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
        return json.loads(resposta.read().decode('utf-8'))


def _consultar_viacep(digitos):
    dados = _buscar_json(f'https://viacep.com.br/ws/{digitos}/json/')
    # A ViaCEP responde {"erro": "true"} quando o CEP não existe
    if dados.get('erro') or not dados.get('localidade'):
        raise CepNaoEncontrado
    return {
        'logradouro': dados.get('logradouro', ''),
        'bairro': dados.get('bairro', ''),
        'cidade': dados.get('localidade', ''),
        'uf': dados.get('uf', ''),
    }


def _consultar_brasilapi(digitos):
    try:
        dados = _buscar_json(f'https://brasilapi.com.br/api/cep/v1/{digitos}')
    except HTTPError as erro:
        # A BrasilAPI responde 404 quando o CEP não existe
        if erro.code == 404:
            raise CepNaoEncontrado from erro
        raise
    if not dados.get('city'):
        raise CepNaoEncontrado
    return {
        'logradouro': dados.get('street', ''),
        'bairro': dados.get('neighborhood', ''),
        'cidade': dados.get('city', ''),
        'uf': dados.get('state', ''),
    }


def consultar_cep(texto):
    """Retorna o endereço do CEP:
    {'cep', 'logradouro', 'bairro', 'cidade', 'uf'}

    Lança CepInvalido, CepNaoEncontrado ou ServicoCepIndisponivel."""
    digitos = limpar_cep(texto)

    chave_cache = f'cep:{digitos}'
    endereco = cache.get(chave_cache)
    if endereco is not None:
        return endereco

    alguma_respondeu = False
    for consultar in (_consultar_viacep, _consultar_brasilapi):
        try:
            endereco = consultar(digitos)
            break
        except CepNaoEncontrado:
            # As bases são diferentes: CEPs gerais de cidades pequenas (ex.:
            # 13520-000, São Pedro/SP) faltam na ViaCEP e existem na
            # BrasilAPI. Por isso "não encontrado" também tenta a próxima
            alguma_respondeu = True
            continue
        except (URLError, HTTPError, TimeoutError, ValueError, OSError):
            # Esta API falhou (fora do ar, lenta ou resposta inválida):
            # tenta a próxima
            continue
    else:
        if alguma_respondeu:
            raise CepNaoEncontrado
        raise ServicoCepIndisponivel(
            'Não foi possível consultar o CEP agora.')

    endereco['cep'] = formatar_cep(digitos)
    cache.set(chave_cache, endereco, TEMPO_CACHE)
    return endereco
