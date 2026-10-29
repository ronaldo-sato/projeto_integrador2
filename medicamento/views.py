from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from . import sugestoes
from .formas import ilustrar
from .models import Medicamento

# Create your views here.

# Tamanhos máximos definidos no model (o banco recusa textos maiores)
MAX_NOME = Medicamento._meta.get_field('nome').max_length
MAX_FABRICANTE = Medicamento._meta.get_field('fabricante').max_length


def validar_tamanho(nome, fabricante):
    """Retorna a mensagem de erro se algum campo passar do tamanho aceito
    pelo banco (evita erro 500), ou None se estiver tudo certo"""
    if len(nome) > MAX_NOME:
        return f'O nome pode ter no máximo {MAX_NOME} caracteres.'
    if len(fabricante) > MAX_FABRICANTE:
        return f'O fabricante pode ter no máximo {MAX_FABRICANTE} caracteres.'
    return None


def renderizar_pagina(request, dados_medicamento=None):
    """Página de medicamentos: formulário de cadastro + tabela. Em caso de
    erro no cadastro, o formulário volta com os dados digitados"""
    return render(request, 'medicamento/listar.html', {
        # ilustrar: define o desenho de cada medicamento (medicamento.forma)
        'medicamentos': ilustrar(
            Medicamento.objects.order_by('nome', 'fabricante')),
        # Se o catálogo do MAPA não foi importado, as sugestões vêm só dos
        # medicamentos já cadastrados (a página avisa)
        'catalogo_mapa': sugestoes.catalogo_disponivel(),
        'dados_medicamento': dados_medicamento or {},
        'max_nome': MAX_NOME,
        'max_fabricante': MAX_FABRICANTE,
    })


@login_required
def cadastrar(request):

    if request.method == 'POST':

        nome = request.POST.get('nome_medicamento', '').strip()
        fabricante = request.POST.get('fabricante', '').strip()

        # Em caso de erro, volta para a página com os dados digitados
        def devolver_formulario():
            return renderizar_pagina(
                request, {'nome': nome, 'fabricante': fabricante})

        # Os dois campos são obrigatórios
        if not nome or not fabricante:
            messages.error(request, 'Preencha o medicamento e o fabricante.')
            return devolver_formulario()

        erro_tamanho = validar_tamanho(nome, fabricante)
        if erro_tamanho:
            messages.error(request, erro_tamanho)
            return devolver_formulario()

        # Permite medicamento com mesmo nome, se for de fabricantes
        # diferentes
        if Medicamento.objects.filter(
                nome__iexact=nome,
                fabricante__iexact=fabricante).exists():

            messages.error(
                request,
                f'O medicamento "{nome}" ' +
                f'do fabricante "{fabricante}" já está cadastrado!')

            return devolver_formulario()

        # Inserir no Banco
        Medicamento.objects.create(nome=nome, fabricante=fabricante)

        messages.success(
            request,
            f'Medicamento "{nome}" ({fabricante}) cadastrado!')

        # Redireciona para a página de medicamentos
        return redirect('medicamento:listar')

    return redirect('medicamento:listar')


@login_required
def listar(request):
    # Busca todos os medicamentos e exibe com o formulário
    return renderizar_pagina(request)


@login_required
# Exclusão só por POST: um link (GET) não consegue apagar dados
@require_POST
def deletar(request, id):
    medicamento = get_object_or_404(Medicamento, id=id)

    nome = medicamento.nome

    medicamento.delete()

    messages.success(request, f'Medicamento "{nome}" removido com sucesso!')

    return redirect('medicamento:listar')


@login_required
def atualizar(request, id):
    # Busca pelo id
    medicamento = get_object_or_404(Medicamento, id=id)

    def renderizar_edicao(nome, fabricante):
        return render(request, 'medicamento/atualizar.html', {
            'medicamento': medicamento,
            'dados': {'nome': nome, 'fabricante': fabricante},
            'max_nome': MAX_NOME,
            'max_fabricante': MAX_FABRICANTE,
        })

    # Se o usuário clicar em Salvar (POST)
    if request.method == 'POST':
        # Pega dados do formulário
        nome_novo = request.POST.get('nome_medicamento', '').strip()
        fabricante_novo = request.POST.get('fabricante', '').strip()

        # Não podem ser em branco
        if not nome_novo or not fabricante_novo:

            # # Mensagem de erro (vazios)
            messages.error(
                request, "Erro: Nome e Fabricante são obrigatórios.")

            # Renderiza edição mantendo o que foi digitado
            return renderizar_edicao(nome_novo, fabricante_novo)

        erro_tamanho = validar_tamanho(nome_novo, fabricante_novo)
        if erro_tamanho:
            messages.error(request, erro_tamanho)
            return renderizar_edicao(nome_novo, fabricante_novo)

        # (Apenas se nome mudou) Verifica duplicidade:
        if (nome_novo != medicamento.nome or
                fabricante_novo != medicamento.fabricante) and \
                Medicamento.objects.filter(
                    nome__iexact=nome_novo,
                    fabricante__iexact=fabricante_novo).exists():

            messages.error(
                request,
                f'Já existe o medicamento "{nome_novo}" para' +
                f' o fabricante "{fabricante_novo}".')

            # Renderiza para edição
            return renderizar_edicao(nome_novo, fabricante_novo)

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
    return renderizar_edicao(medicamento.nome, medicamento.fabricante)


@login_required
@require_GET
def sugerir(request):
    """Sugestões de nomes para o campo do cadastro (medicamento.js): busca
    aproximada nos medicamentos já cadastrados e no catálogo do MAPA"""
    consulta = request.GET.get('q', '').strip()[:100]
    if len(consulta) < 2:
        return JsonResponse({'sugestoes': []})
    return JsonResponse({'sugestoes': sugestoes.sugerir(consulta)})
