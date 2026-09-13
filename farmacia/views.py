from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404

from .models import Farmacia

# Create your views here.

# POST: processa e redireciona (ou renderiza)
# GET: renderiza uma página


def cadastrar(request):
    if request.method == 'POST':

        # Pegar dados do formulário, tratando espaços vazios
        nome = request.POST.get('nome_farmacia').strip()
        endereco = request.POST.get('endereco').strip()

        # Verifica se já existe uma farmácia com este nome exato
        # nome__iexact ignora maiúsculas/minúsculas
        # Não pode farmácias com mesmo nome e endereços iguais
        if Farmacia.objects.filter(
                nome__iexact=nome,
                endereco__iexact=endereco).exists():
            # Envia mensagem de erro
            messages.error(
                request,
                f'A farmácia "{nome}" no endereço "{endereco}"' +
                ' já está cadastrada!')

            # 'app_name:view_name'
            return redirect('base:index')

        # Se não existir, cadastra
        if nome and endereco:  # por segurança, é uma verificação importante

            Farmacia.objects.create(nome=nome, endereco=endereco)

            # Mensagem de cadastrada
            messages.success(request, f'Farmácia "{nome}" cadastrada!')

        # Redireciona para tabela de farmácias cadastradas
        # return redirect('farmacia:listar')
        return redirect('base:index')

    return redirect('base:index')


def listar(request):
    # Busca todas as farmácias no banco
    farmacias = Farmacia.objects.all()

    # Renderiza a tabela de farmácias
    return render(
        request,
        'farmacia/listar.html',
        {'farmacias': farmacias,
         'titulo': 'Farmácias Cadastradas'})


def deletar(request, id):
    # Busca a farmácia pelo id
    farmacia = get_object_or_404(Farmacia, id=id)
    nome = farmacia.nome

    # Apaga a respectiva farmácia
    farmacia.delete()

    # Mensagem de deletada
    messages.success(request, f'Farmácia "{nome}" removida com sucesso!')

    # Redireciona para a tabela de farmácias cadastradas
    return redirect('farmacia:listar')


def atualizar(request, id):
    # Busca a farmácia pelo id
    farmacia = get_object_or_404(Farmacia, id=id)
    title = 'Editar Farmácias'
    heading = 'Editar Registro'

    # Se o usuário clicar em Salvar (POST)
    if request.method == 'POST':
        # Pega dados do formulário
        nome_novo = request.POST.get('nome_farmacia').strip()
        endereco_novo = request.POST.get('endereco').strip()

        # Não podem ser em branco
        if not nome_novo or not endereco_novo:
            # Mensagem de erro (vazios)
            messages.error(request, "Erro: Nome ou Endereço é obrigatório.")
            # Renderiza edição
            return render(
                # request, 'farmacia/atualiza.html', {'farmacia': farmacia})
                request,
                'farmacia/atualizar.html',
                {'farmacia': farmacia,
                 'title': title,
                 'heading': heading})

        # (Apenas se nome mudou) Verifica duplicidade:
        # Não pode duas farmácias com mesmo nome
        if nome_novo != farmacia.nome and \
                Farmacia.objects.filter(nome=nome_novo).exists():
            # Mensagem de erro
            messages.error(
                request,
                f'Já existe outra farmácia com o nome "{nome_novo}".')
            # Renderiza para edição
            return render(
                request,
                'farmacia/atualiza.html',
                {'farmacia': farmacia,
                 'title': title,
                 'heading': heading})

        # Se os campos continuarem iguais, mas apenas clicar
        # no botão Alterar
        if nome_novo == farmacia.nome and endereco_novo == farmacia.endereco:
            messages.warning(
                request,
                f'Não houve alterações nos dados de {farmacia.nome}')
            return redirect('farmacia:listar')

        # Atualiza os campos do objeto
        farmacia.nome = nome_novo
        farmacia.endereco = endereco_novo

        # Salva as "alterações" no banco (se algum dos campos
        # for o mesmo, sobreescreve)
        farmacia.save()

        # Mensagem de atualização
        messages.success(
            request,
            f'Farmácia "{nome_novo}" atualizada com sucesso!')

        # Redireciona para a tabela de farmácias cadastradas
        return redirect('farmacia:listar')

    # Se clicar em Editar, exibe o formulário com os dados atuais
    return render(request,
                  'farmacia/atualiza.html',
                  {'farmacia': farmacia,
                   'title': title,
                   'heading': heading})
