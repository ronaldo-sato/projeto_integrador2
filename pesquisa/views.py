from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import render, redirect

# Create your views here.

from farmacia.models import EstabelecimentoMapa
from preco.models import Preco
from medicamento.formas import ilustrar
from medicamento.models import Medicamento

# Create your views here.


@login_required
def pesquisar(request):
    # A pesquisa usa GET (só consulta, não altera dados): o endereço do
    # resultado pode ser salvo, compartilhado e o botão Voltar funciona
    context = {
        'medicamentos_unicos': Medicamento.objects.values('nome')
        .distinct().order_by('nome'),
    }

    # Para pesquisar os preços de diferentes fabricantes, a busca deve
    # ser pelo nome
    medicamento_nome = request.GET.get('medicamento_nome')

    # Primeira visita à página: só mostra o formulário de pesquisa
    if medicamento_nome is None:
        return render(request, 'pesquisa/precos.html', context)

    if not medicamento_nome.strip():

        messages.error(
            request, 'Selecione um medicamento para pesquisar.')

        return render(request, 'pesquisa/precos.html', context)

    # Busca preços filtrando pelo nome (registrado_mapa: o estabelecimento
    # tem registro ativo no MAPA, para exibir o selo no resultado)
    precos = Preco.objects.filter(
        medicamento__nome__iexact=medicamento_nome) \
        .select_related('farmacia', 'medicamento') \
        .annotate(registrado_mapa=Exists(EstabelecimentoMapa.objects.filter(
            cnpj=OuterRef('farmacia__cnpj'),
            situacao=EstabelecimentoMapa.Situacao.ATIVO))) \
        .order_by('-data_hora')

    # Pegar da lista de preços apenas o mais recente por farmácia (
    # considerando diferentes marcas)
    precos_unicos = {}
    for preco in precos:
        # para cada farmácia, um único medicamento de diferentes marcas
        chave = (preco.farmacia_id, preco.medicamento_id)
        if chave not in precos_unicos:
            precos_unicos[chave] = preco

    # Encontrar o menor preço na lista
    lista_precos = list(precos_unicos.values())

    lista_precos.sort(key=lambda x: x.preco)

    menor_preco = None
    maior_preco = None

    if lista_precos:
        # Valores em Decimal: o template compara cada preço com o menor
        # para destacá-lo (inclusive empates)
        menor_preco = lista_precos[0].preco
        maior_preco = lista_precos[-1].preco

    context.update({
        'pesquisou': True,
        'precos': lista_precos,
        'medicamento_nome': medicamento_nome,
        # Desenho ilustrativo do medicamento pesquisado (todas as marcas têm
        # o mesmo nome, então a primeira basta)
        'forma': ilustrar([lista_precos[0].medicamento])[0].forma
        if lista_precos else None,
        'menor_preco': menor_preco,
        # Diferença entre o mais caro e o mais barato (economia possível)
        'economia': maior_preco - menor_preco if lista_precos else None,
        'opcoes_menor_preco': [
            p for p in lista_precos if p.preco == menor_preco],
    })
    return render(request, 'pesquisa/precos.html', context)


@login_required
def pesquisar_por_id(request):
    # formulário usando select, pegando id do medicamento
    medicamento_id = request.POST.get('medicamento_id')

    if not medicamento_id:

        messages.error(
            request, 'Selecione um medicamento para pesquisar.')

        return redirect('base:index')

    # Busca preços filtrando pelo ID
    precos = Preco.objects.filter(medicamento_id=medicamento_id) \
        .select_related('farmacia', 'medicamento') \
        .order_by('-data_hora')

    # Pegar da lista de preços apenas o mais recente por farmácia
    precos_unicos = {}
    for preco in precos:

        if preco.farmacia_id not in precos_unicos:
            precos_unicos[preco.farmacia_id] = preco

    # Encontrar o menor preço na lista
    lista_precos = list(precos_unicos.values())

    lista_precos.sort(key=lambda x: x.preco)

    menor_preco = None
    medicamento = None

    if lista_precos:
        # Convertendo para float, na tabela o valor como str não estava
        # sendo destacado
        menor_preco = float(
            lista_precos[0].preco)
        # min(preco.preco for preco in lista_precos))

    else:

        medicamento = Medicamento.objects.filter(
            id=medicamento_id).first()

    return render(
        request,
        'pesquisa/precos.html',
        {
            'precos': lista_precos,
            'medicamento': medicamento,
            'menor_preco': menor_preco,
        })
