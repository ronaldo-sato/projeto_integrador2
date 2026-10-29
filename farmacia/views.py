from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from . import sugestoes
from .cep import (CepInvalido, CepNaoEncontrado, ServicoCepIndisponivel,
                  consultar_cep, formatar_cep, limpar_cep)
from .cnpj import (CnpjInvalido, CnpjNaoEncontrado, ServicoCnpjIndisponivel,
                   formatar_cnpj, validar_cnpj)
from .models import UFS, EstabelecimentoMapa, Farmacia, montar_endereco

# Create your views here.

# POST: processa e redireciona (ou renderiza)
# GET: renderiza uma página

# Campos do formulário de estabelecimento (nome do campo no POST)
CAMPOS = ['nome', 'tipo', 'cnpj', 'cep', 'logradouro', 'numero', 'complemento',
          'bairro', 'cidade', 'uf']
# Campos que o usuário precisa preencher (CNPJ, CEP e complemento são opcionais)
OBRIGATORIOS = {
    'nome': 'o nome', 'logradouro': 'o logradouro', 'numero': 'o número',
    'bairro': 'o bairro', 'cidade': 'a cidade', 'uf': 'a UF',
}
# Tamanhos máximos definidos no model (o banco recusa textos maiores)
TAMANHOS = {campo: Farmacia._meta.get_field(campo).max_length
            for campo in CAMPOS if campo not in ('tipo', 'cep', 'cnpj')}
MAX_ENDERECO = Farmacia._meta.get_field('endereco').max_length


def ler_formulario(request):
    """Lê os campos do formulário, tirando espaços nas pontas"""
    dados = {campo: request.POST.get(campo, '').strip() for campo in CAMPOS}
    # O campo do nome mantém o nome usado desde a primeira versão
    dados['nome'] = request.POST.get('nome_farmacia', '').strip()
    dados['uf'] = dados['uf'].upper()
    return dados


def validar(dados):
    """Valida os dados e completa o CEP formatado e o endereço montado.
    Retorna a mensagem de erro, ou None se estiver tudo certo"""
    faltando = [rotulo for campo, rotulo in OBRIGATORIOS.items()
                if not dados[campo]]
    if faltando:
        return 'Preencha ' + ', '.join(faltando) + '.'

    if dados['tipo'] not in Farmacia.Tipo.values:
        return 'Escolha um tipo de estabelecimento válido.'

    if dados['uf'] not in UFS:
        return 'Escolha uma UF válida.'

    if dados['cep']:
        try:
            dados['cep'] = formatar_cep(limpar_cep(dados['cep']))
        except CepInvalido:
            return 'O CEP deve ter 8 dígitos (ex.: 01310-100).'

    # CNPJ é opcional; se informado, os dígitos verificadores precisam conferir
    if dados['cnpj']:
        try:
            dados['cnpj'] = validar_cnpj(dados['cnpj'])
        except CnpjInvalido as erro:
            return str(erro)

    for campo, maximo in TAMANHOS.items():
        if len(dados[campo]) > maximo:
            rotulo = Farmacia._meta.get_field(campo).verbose_name
            return f'O campo {rotulo} pode ter no máximo {maximo} caracteres.'

    dados['endereco'] = montar_endereco(
        dados['logradouro'], dados['numero'], dados['complemento'],
        dados['bairro'], dados['cidade'], dados['uf'])
    if len(dados['endereco']) > MAX_ENDERECO:
        return 'O endereço completo ficou longo demais. Abrevie algum campo.'

    return None


def contexto_formulario(dados):
    """Dados comuns aos formulários de cadastro e de edição"""
    cnpj = dados.get('cnpj', '')
    return {
        'dados': dados,
        # CNPJ válido aparece formatado; o digitado com erro volta como estava
        'cnpj_exibido': formatar_cnpj(cnpj) if len(cnpj) == 14 and cnpj.isdigit() else cnpj,
        'tipos': Farmacia.Tipo.choices,
        'ufs': UFS,
        'tamanhos': TAMANHOS,
        'dados_mapa_disponiveis': sugestoes.dados_disponiveis(),
    }


def com_registro_mapa(farmacias):
    """Acrescenta registrado_mapa=True aos estabelecimentos cujo CNPJ tem
    registro ativo no MAPA (calculado na hora, sempre atualizado)"""
    return farmacias.annotate(registrado_mapa=Exists(
        EstabelecimentoMapa.objects.filter(
            cnpj=OuterRef('cnpj'), situacao=EstabelecimentoMapa.Situacao.ATIVO)))


def renderizar_pagina(request, dados=None):
    """Página de estabelecimentos: formulário de cadastro + tabela. Em caso
    de erro no cadastro, o formulário volta com os dados digitados"""
    context = contexto_formulario(dados or {'tipo': Farmacia.Tipo.FARMACIA})
    context['farmacias'] = com_registro_mapa(Farmacia.objects.order_by('nome', 'endereco'))
    return render(request, 'farmacia/listar.html', context)


def cnpj_em_uso(dados, ignorar_id=None):
    """Cada CNPJ é uma unidade e só pode ser cadastrado uma vez"""
    if not dados['cnpj']:
        return False
    outros = Farmacia.objects.filter(cnpj=dados['cnpj'])
    if ignorar_id:
        outros = outros.exclude(id=ignorar_id)
    return outros.exists()


def existe_duplicada(dados, ignorar_id=None):
    """Verifica se já existe estabelecimento com o mesmo nome no mesmo
    endereço (unidades da mesma rede em endereços diferentes são
    permitidas). nome__iexact ignora maiúsculas/minúsculas"""
    repetidas = Farmacia.objects.filter(
        nome__iexact=dados['nome'], endereco__iexact=dados['endereco'])
    if ignorar_id:
        repetidas = repetidas.exclude(id=ignorar_id)
    return repetidas.exists()


@login_required
def cadastrar(request):
    if request.method == 'POST':

        dados = ler_formulario(request)

        erro = validar(dados)
        if erro:
            messages.error(request, erro)
            # Volta para a página com os dados digitados
            return renderizar_pagina(request, dados)

        # Não pode o mesmo estabelecimento no mesmo endereço
        if existe_duplicada(dados):
            messages.error(
                request,
                f'"{dados["nome"]}" no endereço "{dados["endereco"]}"' +
                ' já está cadastrado!')
            return renderizar_pagina(request, dados)

        if cnpj_em_uso(dados):
            messages.error(
                request,
                f'Já existe um estabelecimento cadastrado com o CNPJ '
                f'{formatar_cnpj(dados["cnpj"])}.')
            return renderizar_pagina(request, dados)

        # Se não existir, cadastra
        Farmacia.objects.create(**{campo: dados[campo] for campo in CAMPOS},
                                endereco=dados['endereco'])

        # Mensagem de cadastrado
        messages.success(request, f'"{dados["nome"]}" cadastrado!')

        # Redireciona para a página de estabelecimentos
        return redirect('farmacia:listar')

    return redirect('farmacia:listar')


@login_required
def listar(request):
    # Busca todos os estabelecimentos e exibe com o formulário
    return renderizar_pagina(request)


@login_required
# Exclusão só por POST: um link (GET) não consegue apagar dados
@require_POST
def deletar(request, id):
    # Busca o estabelecimento pelo id
    farmacia = get_object_or_404(Farmacia, id=id)
    nome = farmacia.nome

    # Apaga o respectivo estabelecimento (e os preços registrados nele)
    farmacia.delete()

    # Mensagem de deletado
    messages.success(request, f'"{nome}" removido com sucesso!')

    # Redireciona para a tabela de estabelecimentos
    return redirect('farmacia:listar')


@login_required
def atualizar(request, id):
    # Busca o estabelecimento pelo id
    farmacia = get_object_or_404(Farmacia, id=id)

    def renderizar_edicao(dados):
        context = contexto_formulario(dados)
        context['farmacia'] = farmacia
        return render(request, 'farmacia/atualizar.html', context)

    # Se o usuário clicar em Salvar (POST)
    if request.method == 'POST':
        dados = ler_formulario(request)

        erro = validar(dados)
        if erro:
            messages.error(request, erro)
            # Renderiza edição mantendo o que foi digitado
            return renderizar_edicao(dados)

        # Não pode haver outro estabelecimento com o mesmo nome e endereço
        if existe_duplicada(dados, ignorar_id=farmacia.id):
            messages.error(
                request,
                f'Já existe "{dados["nome"]}" no endereço ' +
                f'"{dados["endereco"]}".')
            return renderizar_edicao(dados)

        if cnpj_em_uso(dados, ignorar_id=farmacia.id):
            messages.error(
                request,
                f'Já existe outro estabelecimento cadastrado com o CNPJ '
                f'{formatar_cnpj(dados["cnpj"])}.')
            return renderizar_edicao(dados)

        # Se os campos continuarem iguais, mas apenas clicar em Salvar
        if all(getattr(farmacia, campo) == dados[campo] for campo in CAMPOS):
            messages.warning(
                request,
                f'Não houve alterações nos dados de {farmacia.nome}')
            return redirect('farmacia:listar')

        # Atualiza os campos do objeto e salva no banco
        for campo in CAMPOS:
            setattr(farmacia, campo, dados[campo])
        farmacia.endereco = dados['endereco']
        farmacia.save()

        # Mensagem de atualização
        messages.success(
            request, f'"{farmacia.nome}" atualizado com sucesso!')

        # Redireciona para a tabela de estabelecimentos
        return redirect('farmacia:listar')

    # Se clicar em Editar, exibe o formulário com os dados atuais
    return renderizar_edicao(
        {campo: getattr(farmacia, campo) for campo in CAMPOS})


@login_required
@require_GET
def buscar_cep(request, cep):
    """Endpoint usado pelo formulário (farmacia.js): devolve em JSON o
    endereço do CEP consultado nas APIs públicas (ver cep.py)"""
    try:
        return JsonResponse(consultar_cep(cep))
    except CepInvalido:
        return JsonResponse(
            {'erro': 'O CEP deve ter 8 dígitos.'}, status=400)
    except CepNaoEncontrado:
        return JsonResponse({'erro': 'CEP não encontrado.'}, status=404)
    except ServicoCepIndisponivel:
        return JsonResponse(
            {'erro': 'Não foi possível consultar o CEP agora. '
                     'Preencha o endereço manualmente.'}, status=503)


@login_required
@require_GET
def buscar_cnpj(request, cnpj):
    """Endpoint usado pelo formulário: devolve em JSON os dados para
    preencher o cadastro (registro no MAPA + Receita + CEP; ver sugestoes.py).
    ?ignorar=<id> evita acusar o próprio estabelecimento na edição"""
    ignorar = request.GET.get('ignorar', '')
    try:
        return JsonResponse(sugestoes.consultar_estabelecimento(
            cnpj, ignorar_id=int(ignorar) if ignorar.isdigit() else None))
    except CnpjInvalido as erro:
        return JsonResponse({'erro': str(erro)}, status=400)
    except CnpjNaoEncontrado:
        return JsonResponse({'erro': 'CNPJ não encontrado.'}, status=404)
    except ServicoCnpjIndisponivel:
        return JsonResponse(
            {'erro': 'Não foi possível consultar o CNPJ agora. '
                     'Preencha os dados manualmente.'}, status=503)


@login_required
@require_GET
def sugerir(request):
    """Sugestões de estabelecimentos registrados no MAPA para o campo de
    nome (busca aproximada; aceita erros de digitação e o começo do CNPJ)"""
    consulta = request.GET.get('q', '').strip()[:100]
    if len(consulta) < 3 or not sugestoes.dados_disponiveis():
        return JsonResponse({'sugestoes': []})
    return JsonResponse({'sugestoes': sugestoes.sugerir(consulta)})
