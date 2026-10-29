"""Ilustração dos medicamentos pela forma farmacêutica.

Não existe base pública com fotos de medicamentos veterinários (o MAPA só
publica texto), então cada medicamento ganha um desenho ilustrativo da sua
forma: comprimido, injetável, pipeta, shampoo... A forma é deduzida das
palavras do nome ('Bravecto Comprimido Mastigável' -> comprimido). Quando o
nome não indica a forma, usa o desenho genérico de medicamento.

Os desenhos ficam em medicamento/templates/medicamento/partials/
sprite_formas.html (um símbolo SVG para cada chave abaixo).
"""
import re
from dataclasses import dataclass

from django.db.models.functions import Lower

from .mapa import normalizar
from .models import ProdutoMapa


@dataclass(frozen=True)
class Forma:
    chave: str    # nome do desenho e da cor (CSS: .ilustracao-<chave>)
    rotulo: str   # texto exibido ao lado do desenho


# Em ordem de prioridade: a primeira regra que combinar com o nome decide.
# As mais específicas vêm antes ('solução injetável' é injetável, não
# líquido). Os padrões são aplicados ao nome normalizado: minúsculas, sem
# acentos e sem pontuação ('Pour-On' -> 'pour on')
REGRAS = [
    # 'vac' no fim da palavra: nomes comerciais de vacinas (Nobivac, Cevac)
    (Forma('vacina', 'Vacina'), r'\bvacin|vac\b|\bbacterina|\btoxoide'),
    (Forma('diagnostico', 'Teste diagnóstico'),
     r'\b(kits?|elisa|diagnostico|snap)\b|test(e|es|s)?\b'),
    (Forma('coleira', 'Coleira / brinco'), r'\b(coleiras?|brincos?)\b'),
    (Forma('shampoo', 'Shampoo / sabonete'),
     r'\b(shampoo|xampu|sabonete|sabao|condicionador)'),
    (Forma('spray', 'Spray'), r'\b(spray|aerossol|aerosol|pulveriza)'),
    (Forma('pipeta', 'Pipeta / pour-on'),
     r'\b(pour ?on|spot ?on|pipetas?|transdermal)\b'),
    (Forma('injetavel', 'Injetável'), r'\b(injet|injec|inj\b)'),
    (Forma('pomada', 'Pomada / pasta'),
     r'\b(pomada|creme|unguento|gel|pasta)\b'),
    (Forma('gotas', 'Gotas / colírio'),
     r'\b(colirio|gotas|otologic[oa]|auricular|otic[oa])\b'),
    (Forma('comprimido', 'Comprimido'),
     r'\b(comprimidos?|comp|mastigave(l|is)|tabletes?|drageas?)\b'),
    (Forma('capsula', 'Cápsula'), r'\bcapsulas?\b'),
    (Forma('po', 'Pó / premix'), r'\b(po|premix|granulado|soluvel|talco)\b'),
    (Forma('liquido', 'Líquido oral'),
     r'\b(suspensao|solucao|liquido|xarope|elixir|emulsao)\b'),
]
REGRAS = [(forma, re.compile(padrao)) for forma, padrao in REGRAS]

# Produto biológico do MAPA cujo nome não indica a forma ('Nobilis Gumboro
# Broiler'): quase sempre é vacina. Usa o mesmo desenho
BIOLOGICO = Forma('vacina', 'Vacina / biológico')
GENERICA = Forma('medicamento', 'Medicamento')

# Todas as formas (usado nos testes para conferir que cada uma tem desenho)
FORMAS = [forma for forma, _ in REGRAS] + [GENERICA]


def identificar_forma(nome, biologico=False):
    """Forma do medicamento a partir do nome. Ex.: 'Ivomec Injetável' ->
    Forma('injetavel', 'Injetável'). biologico: o produto é biológico no
    catálogo do MAPA"""
    texto = normalizar(nome)
    for forma, padrao in REGRAS:
        if padrao.search(texto):
            return forma
    return BIOLOGICO if biologico else GENERICA


def ilustrar(medicamentos):
    """Define medicamento.forma em cada medicamento da lista. Consulta o
    catálogo do MAPA para saber quais são biológicos (uma consulta ao banco
    para a lista toda)"""
    medicamentos = list(medicamentos)
    nomes = {m.nome.lower() for m in medicamentos}
    biologicos = set(
        ProdutoMapa.objects.annotate(nome_minusculo=Lower('nome'))
        .filter(nome_minusculo__in=nomes,
                natureza=ProdutoMapa.Natureza.BIOLOGICO)
        .values_list('nome_minusculo', flat=True))
    for m in medicamentos:
        m.forma = identificar_forma(m.nome, m.nome.lower() in biologicos)
    return medicamentos
