"""Sugestões de nomes para o cadastro de medicamentos.

Junta duas fontes, usando o índice de vizinhos mais próximos (busca.py):
- os medicamentos já cadastrados no sistema (aparecem primeiro, para o
  mesmo medicamento não ser cadastrado com nomes diferentes);
- o catálogo de produtos registrados no MAPA (importar_produtos_mapa).
"""
import threading

from django.db.models import Max

from .busca import IndiceKNN
from .formas import identificar_forma
from .mapa import normalizar
from .models import Medicamento, ProdutoMapa

# Bônus para os medicamentos já cadastrados no sistema
BONUS_CADASTRADOS = 0.1
MAX_NOME = Medicamento._meta.get_field('nome').max_length
MAX_FABRICANTE = Medicamento._meta.get_field('fabricante').max_length

# O índice do catálogo do MAPA (milhares de nomes) é montado uma vez e
# guardado em memória; só é refeito quando o catálogo é reimportado
_trava = threading.Lock()
_cache = {'versao': None, 'indice': None, 'produtos': {}}


def _versao_catalogo():
    """Muda sempre que o catálogo é reimportado"""
    ativos = ProdutoMapa.objects.exclude(situacao=ProdutoMapa.Situacao.CANCELADO)
    return (ativos.count(), ativos.aggregate(ultima=Max('atualizado_em'))['ultima'])


def _indice_mapa():
    versao = _versao_catalogo()
    with _trava:
        if _cache['versao'] != versao:
            produtos = {
                p.id: p for p in ProdutoMapa.objects.exclude(
                    situacao=ProdutoMapa.Situacao.CANCELADO)}
            _cache['indice'] = IndiceKNN((pid, p.nome) for pid, p in produtos.items())
            _cache['produtos'] = produtos
            _cache['versao'] = versao
        return _cache['indice'], _cache['produtos']


def encurtar(texto, limite):
    """Ajusta o texto ao tamanho do campo do cadastro. Nomes longos do MAPA
    costumam ser 'NOME COMERCIAL - descrição': fica só o nome comercial"""
    texto = texto.strip()
    if len(texto) <= limite:
        return texto
    if ' - ' in texto and len(texto.split(' - ')[0]) <= limite:
        return texto.split(' - ')[0].strip()
    return texto[:limite].rsplit(' ', 1)[0].strip()


def sugerir(consulta, k=8):
    """Lista de sugestões (dicionários) para o texto digitado"""
    resultados = []

    # 1. Medicamentos já cadastrados no sistema (poucos: índice na hora).
    # O mesmo nome com várias marcas vira uma sugestão só, listando as marcas
    locais = {}
    for m in Medicamento.objects.order_by('fabricante'):
        grupo = locais.setdefault(normalizar(m.nome), {'nome': m.nome, 'fabricantes': []})
        grupo['fabricantes'].append(m.fabricante)
    indice_local = IndiceKNN((chave, g['nome']) for chave, g in locais.items())
    for chave, nota in indice_local.vizinhos(consulta, k=k):
        grupo = locais[chave]
        forma = identificar_forma(grupo['nome'])
        resultados.append({
            'nome': grupo['nome'], 'fabricante': ', '.join(grupo['fabricantes']),
            'forma': forma.chave, 'forma_rotulo': forma.rotulo,
            'fonte': 'cadastrado', 'nome_completo': grupo['nome'], 'natureza': '',
            'licenca_provisoria': False, 'animais_producao': None,
            'nota': min(nota + BONUS_CADASTRADOS, 1.0),
        })

    # 2. Catálogo do MAPA
    indice_mapa, produtos = _indice_mapa()
    for pid, nota in indice_mapa.vizinhos(consulta, k=k):
        p = produtos[pid]
        # O nome completo do MAPA diz mais sobre a forma que o encurtado
        forma = identificar_forma(
            p.nome, p.natureza == ProdutoMapa.Natureza.BIOLOGICO)
        resultados.append({
            'forma': forma.chave, 'forma_rotulo': forma.rotulo,
            'nome': encurtar(p.nome, MAX_NOME),
            'fabricante': encurtar(p.empresa, MAX_FABRICANTE),
            'fonte': 'mapa',
            'nome_completo': p.nome,
            'natureza': p.get_natureza_display() if p.natureza else '',
            'licenca_provisoria': p.situacao == ProdutoMapa.Situacao.LICENCA_PROVISORIA,
            'animais_producao': p.animais_producao,
            'nota': nota,
        })

    # Ordena pela nota e remove repetições (mesmo nome e fabricante)
    resultados.sort(key=lambda r: r['nota'], reverse=True)
    vistos, unicos = set(), []
    for r in resultados:
        chave = (normalizar(r['nome']), normalizar(r['fabricante']))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    return unicos[:k]


def catalogo_disponivel():
    return ProdutoMapa.objects.exists()
