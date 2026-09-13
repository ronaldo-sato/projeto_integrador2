from django.contrib import messages
from django.shortcuts import render, redirect

# Create your views here.

from preco.models import Preco
from medicamento.models import Medicamento

# Create your views here.


def pesquisar(request):
    # Para pesquisar os preços de diferentes fabricantes, a busca deve
    # ser pelo nome
    medicamento_nome = request.POST.get('medicamento_nome')

    if not medicamento_nome:

        messages.error(
            request, 'Selecione um medicamento para pesquisar.')

        return redirect('base:index')

    # Busca preços filtrando pelo nome
    precos = Preco.objects.filter(
        medicamento__nome__iexact=medicamento_nome) \
        .select_related('farmacia', 'medicamento') \
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
    medicamento = None

    if lista_precos:
        # Convertendo para float, na tabela o valor como str não estava
        # sendo destacado
        menor_preco = float(lista_precos[0].preco)

    return render(
        request,
        'pesquisa/precos.html',
        {
            'precos': lista_precos,
            'medicamento_nome': medicamento_nome,
            'menor_preco': menor_preco,
        })


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
