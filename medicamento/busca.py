"""Busca aproximada de nomes de medicamentos (K vizinhos mais próximos).

Ideia: cada nome vira um vetor e a busca devolve os K nomes cujos vetores
estão mais próximos do vetor do texto digitado.

1. Trigramas: o nome é quebrado em pedaços de 3 letras. "bravecto" vira
   " br", "bra", "rav", "ave", "vec", "ect", "cto", "to ". Um erro de
   digitação ("bravekto") muda só alguns pedaços; a maioria continua igual,
   então os nomes continuam parecidos.

2. TF-IDF: pedaços que aparecem em quase todos os nomes ("cao", "mg ")
   ajudam pouco a diferenciar e recebem peso menor; pedaços raros recebem
   peso maior. peso = frequência no nome x log(N / nº de nomes com o pedaço)

3. Similaridade de cosseno: mede o ângulo entre os vetores (1 = iguais,
   0 = nada em comum), sem ser afetada pelo tamanho do nome.

4. Índice invertido: para cada trigrama guardamos os nomes que o contêm.
   Assim a busca só compara a consulta com os nomes que têm algum pedaço em
   comum, em vez de percorrer o catálogo inteiro.

5. Reordenação pela distância de edição: os trigramas escolhem rápido os
   candidatos mais próximos, mas favorecem nomes curtos. Os melhores
   candidatos são então reordenados pela distância de Levenshtein entre as
   palavras (quantas letras precisam mudar para uma virar a outra):
   "bravekto" está a 1 letra de "bravecto" e a 5 de "bravecilin".

Como o texto é normalizado antes (sem acentos, minúsculas, sem pontuação) e
os trigramas são calculados por palavra, a busca também funciona com acentos
diferentes, maiúsculas e palavras fora de ordem.
"""
import heapq
import math
from collections import Counter, defaultdict

from .mapa import normalizar

TAMANHO_NGRAMA = 3
# Bônus para nomes que começam com o que foi digitado (autocompletar)
BONUS_PREFIXO = 0.15
# Quantos candidatos dos trigramas são reordenados pela distância de edição
CANDIDATOS_REORDENACAO = 50
# Peso de cada parte na nota final (trigramas x distância de edição)
PESO_TRIGRAMAS = 0.5


def levenshtein(a, b):
    """Distância de edição: nº mínimo de letras inseridas, removidas ou
    trocadas para transformar a em b ('bravekto' -> 'bravecto' = 1)"""
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, letra_a in enumerate(a, start=1):
        atual = [i]
        for j, letra_b in enumerate(b, start=1):
            atual.append(min(anterior[j] + 1,                        # remoção
                             atual[j - 1] + 1,                       # inserção
                             anterior[j - 1] + (letra_a != letra_b)))  # troca
        anterior = atual
    return anterior[-1]


def similaridade_palavras(consulta, texto):
    """Para cada palavra digitada, a palavra mais parecida do texto (de 0 a
    1, pela distância de edição); devolve a média. Uma palavra digitada pela
    metade conta como igual ao começo da palavra do texto ('brav' ~ 'bravecto')"""
    palavras_texto = texto.split()
    if not palavras_texto:
        return 0.0
    notas = []
    for palavra in consulta.split():
        melhor = 0.0
        for alvo in palavras_texto:
            # Compara também com o começo da palavra (usuário ainda digitando)
            for candidato in {alvo, alvo[:len(palavra)]}:
                maior = max(len(palavra), len(candidato))
                melhor = max(melhor, 1 - levenshtein(palavra, candidato) / maior)
        notas.append(melhor)
    return sum(notas) / len(notas)


def trigramas(texto):
    """Pedaços de 3 letras de cada palavra (com espaço nas pontas, para
    marcar início e fim): 'meloxicam 2mg' -> ' me', 'mel', ..., ' 2m', '2mg', 'mg '"""
    pedacos = []
    for palavra in normalizar(texto).split():
        palavra = f' {palavra} '
        if len(palavra) <= TAMANHO_NGRAMA:
            pedacos.append(palavra)
        else:
            pedacos.extend(palavra[i:i + TAMANHO_NGRAMA]
                           for i in range(len(palavra) - TAMANHO_NGRAMA + 1))
    return pedacos


class IndiceKNN:
    """Índice de K vizinhos mais próximos sobre trigramas com TF-IDF.

    documentos: lista de (identificador, texto). O identificador pode ser
    qualquer valor (ex.: ('mapa', 42)) e é devolvido na busca."""

    def __init__(self, documentos):
        self.ids = []
        self.textos_normalizados = []
        contagens = []
        documentos_por_trigrama = Counter()

        for identificador, texto in documentos:
            contagem = Counter(trigramas(texto))
            if not contagem:
                continue
            self.ids.append(identificador)
            self.textos_normalizados.append(normalizar(texto))
            contagens.append(contagem)
            documentos_por_trigrama.update(contagem.keys())

        total = len(contagens)
        # IDF: trigramas raros pesam mais (o +1 evita divisão por zero)
        self.idf = {t: math.log((total + 1) / (n + 1)) + 1
                    for t, n in documentos_por_trigrama.items()}
        self.idf_desconhecido = math.log(total + 1) + 1

        # Índice invertido: trigrama -> [(posição do documento, peso)]
        self.invertido = defaultdict(list)
        for posicao, contagem in enumerate(contagens):
            vetor = self._vetor(contagem)
            for trigrama, peso in vetor.items():
                self.invertido[trigrama].append((posicao, peso))

    def __len__(self):
        return len(self.ids)

    def _vetor(self, contagem):
        """Vetor TF-IDF normalizado (tamanho 1), para o produto escalar já
        ser a similaridade de cosseno"""
        vetor = {t: n * self.idf.get(t, self.idf_desconhecido)
                 for t, n in contagem.items()}
        norma = math.sqrt(sum(p * p for p in vetor.values())) or 1.0
        return {t: p / norma for t, p in vetor.items()}

    def vizinhos(self, consulta, k=8, similaridade_minima=0.2):
        """Os k documentos mais parecidos com a consulta:
        [(identificador, similaridade)], do mais parecido para o menos"""
        consulta_normalizada = normalizar(consulta)
        contagem = Counter(trigramas(consulta))
        if not contagem:
            return []
        vetor = self._vetor(contagem)

        # Produto escalar só com os documentos que têm algum trigrama em comum
        pontuacao = defaultdict(float)
        for trigrama, peso in vetor.items():
            for posicao, peso_documento in self.invertido.get(trigrama, ()):
                pontuacao[posicao] += peso * peso_documento

        # Os melhores candidatos pelos trigramas são reordenados combinando a
        # nota dos trigramas com a semelhança das palavras (Levenshtein)
        candidatos = heapq.nlargest(
            CANDIDATOS_REORDENACAO, pontuacao.items(), key=lambda par: par[1])
        notas = []
        for posicao, cosseno in candidatos:
            texto = self.textos_normalizados[posicao]
            nota = (PESO_TRIGRAMAS * cosseno +
                    (1 - PESO_TRIGRAMAS) * similaridade_palavras(consulta_normalizada, texto))
            if texto.startswith(consulta_normalizada):
                nota += BONUS_PREFIXO
            notas.append((posicao, nota))

        melhores = heapq.nlargest(k, notas, key=lambda par: par[1])
        return [(self.ids[posicao], round(min(valor, 1.0), 3))
                for posicao, valor in melhores if valor >= similaridade_minima]
