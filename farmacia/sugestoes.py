"""Preenchimento do cadastro de estabelecimentos a partir de dados públicos.

- Busca por nome: sugere estabelecimentos registrados no MAPA usando o
  índice de vizinhos mais próximos (medicamento/busca.py), que aceita erros
  de digitação. O município entra no texto indexado, então "cobasi
  campinas" encontra a unidade de Campinas.
- Consulta por CNPJ: junta o registro no MAPA (se houver), os dados da
  Receita Federal (endereço) e a consulta de CEP (endereço bem escrito, com
  acentos, em vez do texto em maiúsculas da Receita).
"""
import re
import threading

from django.db.models import Max

from medicamento.busca import IndiceKNN
from .cep import CepInvalido, CepNaoEncontrado, ServicoCepIndisponivel, consultar_cep
from .cnpj import (CnpjNaoEncontrado, ServicoCnpjIndisponivel, consultar_receita,
                   formatar_cnpj, validar_cnpj)
from .mapa import ATIVIDADES_VAREJO, sugerir_tipo
from .models import EstabelecimentoMapa, Farmacia

# Índice em memória (cerca de 22 mil nomes): montado na primeira busca e
# refeito só quando os dados do MAPA são reimportados
_trava = threading.Lock()
_cache = {'versao': None, 'indice': None}


def _estabelecimentos_de_varejo():
    """Registros ativos de quem vende ao público (comerciante/manipulador)"""
    filtro = None
    for atividade in ATIVIDADES_VAREJO:
        condicao = EstabelecimentoMapa.objects.filter(atividades__contains=atividade)
        filtro = condicao if filtro is None else filtro | condicao
    return filtro.filter(situacao=EstabelecimentoMapa.Situacao.ATIVO)


def _indice():
    registros = _estabelecimentos_de_varejo()
    versao = (registros.count(), registros.aggregate(ultima=Max('atualizado_em'))['ultima'])
    with _trava:
        if _cache['versao'] != versao:
            textos = registros.values_list('cnpj', 'nome_fantasia', 'razao_social', 'municipio')
            _cache['indice'] = IndiceKNN(
                (cnpj, f'{fantasia or razao} {municipio}')
                for cnpj, fantasia, razao, municipio in textos)
            _cache['versao'] = versao
        return _cache['indice']


def dados_disponiveis():
    return EstabelecimentoMapa.objects.exists()


def _ja_cadastrados(cnpjs, ignorar_id=None):
    cadastrados = Farmacia.objects.filter(cnpj__in=cnpjs)
    if ignorar_id:
        cadastrados = cadastrados.exclude(id=ignorar_id)
    return set(cadastrados.values_list('cnpj', flat=True))


def sugerir(consulta, k=8):
    """Estabelecimentos registrados no MAPA parecidos com o texto digitado
    (nome, ou o começo do CNPJ)"""
    digitos = re.sub(r'\D', '', consulta)
    if len(digitos) >= 5 and len(digitos) >= len(consulta.replace(' ', '')) * 0.6:
        # Digitou um CNPJ: busca pelo começo dos números
        cnpjs = list(_estabelecimentos_de_varejo().filter(cnpj__startswith=digitos)
                     .values_list('cnpj', flat=True)[:k])
    else:
        cnpjs = [cnpj for cnpj, _ in _indice().vizinhos(consulta, k=k)]

    registros = EstabelecimentoMapa.objects.in_bulk(cnpjs, field_name='cnpj')
    cadastrados = _ja_cadastrados(cnpjs)
    return [{
        'cnpj': cnpj,
        'cnpj_formatado': formatar_cnpj(cnpj),
        'nome': registros[cnpj].nome,
        'razao_social': registros[cnpj].razao_social,
        'municipio': registros[cnpj].municipio,
        'uf': registros[cnpj].uf,
        'atividades': registros[cnpj].atividades,
        'ja_cadastrado': cnpj in cadastrados,
    } for cnpj in cnpjs if cnpj in registros]


def consultar_estabelecimento(cnpj, ignorar_id=None):
    """Tudo o que se sabe sobre o CNPJ, pronto para preencher o formulário.

    Lança CnpjInvalido; CnpjNaoEncontrado ou ServicoCnpjIndisponivel só
    quando nem a Receita nem o MAPA trazem dados."""
    digitos = validar_cnpj(cnpj)
    registro = EstabelecimentoMapa.objects.filter(cnpj=digitos).first()

    dados = {
        'cnpj': digitos, 'cnpj_formatado': formatar_cnpj(digitos),
        'nome': registro.nome if registro else '',
        'cep': '', 'logradouro': '', 'numero': '', 'complemento': '',
        'bairro': '', 'cidade': registro.municipio if registro else '',
        'uf': registro.uf if registro else '',
        'situacao_receita': '',
        'endereco_completo': False,
        'mapa': {
            'registro': registro.registro,
            'situacao': registro.get_situacao_display(),
            'ativo': registro.situacao == EstabelecimentoMapa.Situacao.ATIVO,
            'atividades': registro.atividades,
        } if registro else None,
        'ja_cadastrado': bool(_ja_cadastrados([digitos], ignorar_id)),
    }

    try:
        receita = consultar_receita(digitos)
    except (CnpjNaoEncontrado, ServicoCnpjIndisponivel):
        if not registro:
            raise
        receita = None  # fica só com o que o MAPA informa (nome, cidade, UF)

    if receita:
        dados['nome'] = dados['nome'] or receita['nome_fantasia'] or receita['razao_social']
        dados['situacao_receita'] = receita['situacao']
        for campo in ('cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf'):
            dados[campo] = receita[campo] or dados[campo]
        dados['endereco_completo'] = bool(receita['logradouro'] and receita['numero'])

        # O CEP traz o endereço bem escrito (a Receita usa maiúsculas, sem
        # acentos e com abreviações: "VL IASI", "TABOAO DA SERRA")
        if receita['cep']:
            try:
                endereco = consultar_cep(receita['cep'])
                for campo in ('logradouro', 'bairro', 'cidade', 'uf'):
                    dados[campo] = endereco[campo] or dados[campo]
            except (CepInvalido, CepNaoEncontrado, ServicoCepIndisponivel):
                pass

    # Ajusta cada campo ao tamanho aceito pelo banco (a Receita às vezes
    # traz complementos longos)
    for campo in ('nome', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade'):
        dados[campo] = dados[campo][:Farmacia._meta.get_field(campo).max_length].strip()
    dados['tipo_sugerido'] = sugerir_tipo(
        dados['nome'], registro.atividades if registro else '')
    return dados
