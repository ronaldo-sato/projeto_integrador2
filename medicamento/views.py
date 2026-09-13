from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404

from .models import Medicamento

# Create your views here.


def cadastrar(request):

    if request.method == 'POST':

        nome = request.POST.get('nome_medicamento').strip()
        fabricante = request.POST.get('fabricante').strip()

        # Permite medicamento com mesmo nome, se for de fabricantes
        # diferentes
        if Medicamento.objects.filter(
                nome__iexact=nome,
                fabricante__iexact=fabricante).exists():

            messages.error(
                request,
                f'O medicamento "{nome}" ' +
                f'do fabricante "{fabricante}" já está cadastrado!')

            return redirect('base:index')

        if nome and fabricante:

            # Inserir no Banco
            Medicamento.objects.create(nome=nome, fabricante=fabricante)

            messages.success(
                request,
                f'Medicamento "{nome}" ({fabricante}) cadastrado!')

        # return redirect('medicamento:listar')
        return redirect('base:index')

    return redirect('base:index')


def listar(request):

    medicamentos = Medicamento.objects.all()

    # Renderiza a tabela de medicamentos
    return render(
        request,
        'medicamento/listar.html',
        {'medicamentos': medicamentos,
         'titulo': 'Medicamentos Cadastrados'})


def deletar(request, id):
    medicamento = get_object_or_404(Medicamento, id=id)

    nome = medicamento.nome

    medicamento.delete()

    messages.success(request, f'Medicamento "{nome}" removido com sucesso!')

    return redirect('medicamento:listar')


def atualizar(request, id):
    # Busca pelo id
    medicamento = get_object_or_404(Medicamento, id=id)

    # Se o usuário clicar em Salvar (POST)
    if request.method == 'POST':
        # Pega dados do formulário
        nome_novo = request.POST.get('nome_medicamento').strip()
        fabricante_novo = request.POST.get('fabricante').strip()

        # Não podem ser em branco
        if not nome_novo or not fabricante_novo:

            # # Mensagem de erro (vazios)
            messages.error(
                request, "Erro: Nome e Fabricante são obrigatórios.")

            # Renderiza edição
            return render(
                request,
                'medicamento/atualizar.html',
                {'medicamento': medicamento})

        # (Apenas se nome mudou) Verifica duplicidade:
        # if nome_novo != medicamento.nome and \
        #         Medicamento.objects.filter(nome=nome_novo).exists():

        if (nome_novo != medicamento.nome or
                fabricante_novo != medicamento.fabricante) and \
                Medicamento.objects.filter(
                    nome__iexact=nome_novo,
                    fabricante__iexact=fabricante_novo).exists():

            # Mensagem de erro
            # messages.error(
            #     request,
            #     f'Já existe outro medicamento com o nome "{nome_novo}".')

            messages.error(
                request,
                f'Já existe o medicamento "{nome_novo}" para' +
                f' o fabricante "{fabricante_novo}".')

            # Renderiza para edição
            return render(
                request,
                'medicamento/atualizar.html',
                {'medicamento': medicamento})

        # Atualiza os campos do objeto
        medicamento.nome = nome_novo
        medicamento.fabricante = fabricante_novo

        # Salva as "alterações" no banco (se algum dos campos
        # for o mesmo, sobreescreve)
        medicamento.save()

        # Mensagem de atualização
        messages.success(
            request, f'Medicamento "{nome_novo}" atualizado com sucesso!')

        # Redireciona para a tabela de medicamentos cadastrados
        return redirect('medicamento:listar')

    # Se clicar em Editar, exibe o formulário com os dados atuais
    return render(
        request,
        'medicamento/atualizar.html',
        {'medicamento': medicamento})
