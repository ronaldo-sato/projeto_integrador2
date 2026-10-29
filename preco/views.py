from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from farmacia.models import Farmacia
from medicamento.formas import ilustrar
from medicamento.models import Medicamento
from .models import Preco

# Create your views here.

# Maior valor que cabe no campo preco (max_digits=8, decimal_places=2)
PRECO_MAXIMO = Decimal('999999.99')


def converter_preco(texto):
    """Converte o valor digitado (aceita vírgula) em Decimal com 2 casas.
    Retorna None se não for um número entre 0 e PRECO_MAXIMO (bloqueia
    negativos, 'nan', 'inf' e valores que não cabem no banco)"""
    try:
        valor = Decimal(texto.strip().replace(',', '.'))
        if not valor.is_finite():
            return None
        valor = valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, AttributeError):
        return None

    if not Decimal('0') <= valor <= PRECO_MAXIMO:
        return None
    return valor


def renderizar_pagina(request, foco=None, medicamento_selecionado='',
                      fabricante_selecionado_id='', farmacia_selecionada_id='',
                      preco_digitado=''):
    """Página de preços: formulário de cadastro + tabela. Em caso de erro,
    o formulário volta com medicamento, fabricante, valor e farmácia que o
    usuário já tinha escolhido.

    foco: id do campo que recebe o cursor ao abrir a página"""

    # Para selecionar fabricantes de determinado medicamento, é preciso
    # manter o estado das interações com o formulário (ver "filtrar")
    fabricantes_filtrados = None
    if medicamento_selecionado:
        fabricantes_filtrados = Medicamento.objects.filter(
            nome__iexact=medicamento_selecionado.strip())

    # .select_related já traz o nome do medicamento e da farmácia
    # associados ao preço, já que na tabela preco tem-se esses ids
    precos = list(Preco.objects.all().select_related('farmacia', 'medicamento'))
    # Desenho ilustrativo de cada medicamento (medicamento.forma)
    ilustrar(p.medicamento for p in precos)

    return render(request, 'preco/listar.html', {
        'precos': precos,
        'farmacias': Farmacia.objects.order_by('nome'),
        # Pegar medicamentos únicos (para listar no select)
        'medicamentos_unicos': Medicamento.objects.values('nome')
        .distinct().order_by('nome'),
        # Todos os fabricantes: o JavaScript da página usa esta lista para
        # mostrar as marcas do medicamento escolhido sem recarregar a página
        'fabricantes_json': list(Medicamento.objects.order_by('fabricante')
                                 .values('id', 'nome', 'fabricante')),
        'fabricantes_filtrados': fabricantes_filtrados,
        'medicamento_selecionado': medicamento_selecionado,
        'fabricante_selecionado_id': fabricante_selecionado_id,
        'farmacia_selecionada_id': farmacia_selecionada_id,
        'preco_digitado': preco_digitado,
        'foco': foco,
    })


@login_required
def cadastrar(request):

    if request.method == 'POST':

        # Para selecionar fabricantes de determinado medicamento, é
        # preciso manter o estado das interações com o formulário (acao)
        # 1a interação: selecionar medicamento
        # 2a interação: selecionar fabricante (a partir de filtrados)
        # Com JavaScript a lista de fabricantes muda sozinha; o botão
        # "filtrar" fica disponível para navegadores sem JavaScript
        acao = request.POST.get('acao_botao')

        medicamento_selecionado = request.POST.get('medicamento_nome', '')

        # Do formulário vem os ids de farmacia e medicamento (são
        # selecionados a partir de listagem)
        farmacia_id = request.POST.get('farmacia_id', '')
        medicamento_id = request.POST.get('medicamento_id', '')
        preco_digitado = request.POST.get('valor_preco', '')

        # Volta para a página mantendo tudo o que já foi preenchido
        # (medicamento, fabricante, valor e farmácia)
        def devolver_formulario(foco=None):
            return renderizar_pagina(
                request, foco=foco,
                medicamento_selecionado=medicamento_selecionado,
                fabricante_selecionado_id=medicamento_id,
                farmacia_selecionada_id=farmacia_id,
                preco_digitado=preco_digitado)

        # Se a ação for filtrar, devolve os fabricantes filtrados e
        # coloca o cursor no campo Fabricante
        if acao == 'filtrar':

            if not medicamento_selecionado:
                messages.error(
                    request,
                    'Selecione um medicamento antes de filtrar as marcas.')
                return devolver_formulario()

            return devolver_formulario(foco='select-fabricante')

        # Todos os campos são obrigatórios
        if not farmacia_id or not medicamento_id or not preco_digitado:

            messages.error(
                request,
                'Por favor, selecione o estabelecimento, o medicamento e' +
                ' informe o valor (todos os campos são obrigatórios).')

            return devolver_formulario()

        # O fabricante escolhido precisa ser do medicamento que está na
        # tela: o usuário pode ter trocado o medicamento depois de filtrar,
        # e o preço seria gravado para o medicamento errado
        if not medicamento_id.isdigit() or not Medicamento.objects.filter(
                id=medicamento_id,
                nome__iexact=medicamento_selecionado.strip()).exists():
            messages.error(
                request,
                'O fabricante escolhido não é do medicamento selecionado. ' +
                'Escolha o fabricante novamente.')
            return devolver_formulario(foco='select-fabricante')

        # Converte valor para decimal (tratando vírgula) e valida
        # se está na faixa permitida
        preco = converter_preco(preco_digitado)
        if preco is None:
            messages.error(
                request,
                'Valor de preço inválido. Informe um valor de 0 a ' +
                '999.999,99 (ex.: 12,50).')
            return devolver_formulario(foco='valor-preco')

        try:
            # Cria o registro na tabela preco
            Preco.objects.create(
                farmacia_id=farmacia_id,
                medicamento_id=medicamento_id,
                preco=preco
            )

            messages.success(request, 'Preço cadastrado com sucesso!')

            # Redireciona para a página de preços (o novo preço aparece
            # no topo da tabela, que é ordenada do mais recente)
            return redirect('preco:listar')

        except Exception:

            messages.error(
                request, 'Erro ao cadastrar preço. Verifique os dados.')
            return devolver_formulario()

    return redirect('preco:listar')


@login_required
def listar(request):
    # Exibe a tabela de preços com o formulário de cadastro
    return renderizar_pagina(request)


@login_required
# Exclusão só por POST: um link (GET) não consegue apagar dados
@require_POST
def deletar(request, id):
    preco = get_object_or_404(Preco, id=id)

    preco.delete()

    messages.success(request, 'Preço removido com sucesso!')

    return redirect('preco:listar')


@login_required
def atualizar(request, id):
    preco = get_object_or_404(Preco, id=id)

    def renderizar_edicao(valor_digitado=None):
        # Em caso de erro, o campo mantém o valor que o usuário digitou
        return render(request, 'preco/atualizar.html', {
            'preco': preco, 'valor_digitado': valor_digitado})

    if request.method == 'POST':
        preco_novo = request.POST.get('valor_preco', '')

        if not preco_novo:

            messages.error(request, "O campo preço é obrigatório.")

            return renderizar_edicao(preco_novo)

        try:
            # Trata a vírgula, converte para decimal e valida a faixa
            valor = converter_preco(preco_novo)
            if valor is None:
                raise ValueError('Valor de preço inválido')
            preco.preco = valor
            preco.save()

            messages.success(
                request, "Preço atualizado com sucesso!")

            return redirect('preco:listar')

        except ValueError:
            messages.error(
                request,
                'Valor de preço inválido. Informe um valor de 0 a ' +
                '999.999,99 (ex.: 12,50).')
            return renderizar_edicao(preco_novo)

    return renderizar_edicao()
