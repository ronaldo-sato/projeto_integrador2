from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils.http import urlencode

from .models import Preco, Farmacia, Medicamento

# Create your views here.


def cadastrar(request):

    farmacias = Farmacia.objects.all()

    # Pegar medicamentos únicos (para listar no select)
    medicamentos_unicos = Medicamento.objects.values('nome') \
        .distinct().order_by('nome')

    if request.method == 'POST':

        # Para selecionar fabricantes de determinado medicamento, é
        # preciso manter o estado das interações com o formulário (acao)
        # 1a interação: selecionar medicamento
        # 2a interação: selecionar fabricante (a partir de filtrados)
        acao = request.POST.get('acao_botao')
        # acao = request.POST.get('acao_botao') == 'filtrar'

        medicamento_selecionado = request.POST.get('medicamento_nome')

        # Se a ação for filtrar, devolve os fabricantes filtrados
        if acao == 'filtrar':  # and medicamento_selecionado:

            # Medicamentos com caracteres especiais precisam ser
            # tratados (codificados corretamente)
            params_url = urlencode(
                {'medicamento_filtro': medicamento_selecionado})

            # Fazer com que o filtrar não vá para o topo da página,
            # incluindo a âncora e construindo a url para o formulário
            url = f'{reverse('base:index')}?{params_url}#preco'

            return redirect(url)

        # Do formulário vem os ids de farmacia e medicamento (são
        # selecionados a partir de listagem)
        farmacia_id = request.POST.get('farmacia_id')
        medicamento_id = request.POST.get('medicamento_id')
        preco_digitado = request.POST.get('valor_preco')
        # data_hora = request.POST.get('data_hora')

        # Todos os campos são obrigatórios
        if not farmacia_id or not medicamento_id or not preco_digitado:

            messages.error(
                request,
                'Por favor, selecione a farmácia, o medicamento e' +
                ' informe o valor (todos os campos são obrigatórios).')

            # Para manter o estado dos fabricantes filtrados em caso
            # de erro
            fabricantes = Medicamento.objects.filter(
                nome=medicamento_selecionado) \
                if medicamento_selecionado else None

            return render(request, 'base/index.html', {
                'farmacias': farmacias,
                'medicamentos_unicos': medicamentos_unicos,
                'fabricantes_filtrados': fabricantes,
                'medicamento_selecionado': medicamento_selecionado,
                'farmacia_selecionada_id': farmacia_id,
                'preco_digitado': preco_digitado,
            })

        try:
            # Converte valor para float/decimal (tratando vírgula
            # se necessário)
            preco = float(preco_digitado.replace(',', '.'))

            # Cria o registro na tabela preco
            Preco.objects.create(
                farmacia_id=farmacia_id,
                medicamento_id=medicamento_id,
                preco=preco
            )

            messages.success(request, 'Preço cadastrado com sucesso!')

            # Redirecionamento para a âncora
            # return redirect('/#preco')
            # Havendo cadastro melhor redirecionar para o home, para que
            # mensagem de sucesso seja visualizada
            return redirect('base:index')

        except Exception:

            messages.error(
                request, 'Erro ao cadastrar preço. Verifique o valor.')

    return redirect('base:index')


def listar(request):

    # .select_related já traz o nome do medicamento e da farmácia
    # associados ao preço, já que na tabela preco tem-se esses ids
    precos = Preco.objects.all().select_related('farmacia', 'medicamento')

    # Renderiza a tabela de preços
    return render(
        request,
        'preco/listar.html',
        {'precos': precos,
         'titulo': 'Preços Cadastrados'})


def deletar(request, id):
    preco = get_object_or_404(Preco, id=id)

    preco.delete()

    return redirect('index')


def atualizar(request, id):
    preco = get_object_or_404(Preco, id=id)

    if request.method == 'POST':
        preco_novo = request.POST.get('valor_preco')

        if not preco_novo:

            messages.error(request, "O campo preço é obrigatório.")

            return render(
                request, 'preco/atualizar.html', {'preco': preco})

        try:
            # Trata a vírgula e converte para float
            preco.preco = float(preco_novo.replace(',', '.'))
            preco.save()

            messages.success(
                request, "Preço atualizado com sucesso!")

            return redirect('preco:listar')

        except ValueError:
            messages.error(request, "Valor de preço inválido.")

    return render(
        request, 'preco/atualizar.html', {'preco': preco})
