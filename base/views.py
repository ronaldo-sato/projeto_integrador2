from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from farmacia.models import Farmacia
from medicamento.models import Medicamento
from preco.models import Preco

# Create your views here.


# def index(request):
#     return render(
#         request,
#         'base/index.html')


def renderizar_index(request, **dados_formulario):
    """Monta a página inicial. Também é usada pelo login e pelo cadastro
    para reabrir a janela de acesso com os dados que o usuário digitou.

    dados_formulario: valores para preencher de volta os formulários"""

    context = {
        # Nome de medicamentos sem repetição (pesquisa rápida da home)
        'medicamentos_unicos': Medicamento.objects.values('nome')
        .distinct().order_by('nome'),
    }

    # Resumo exibido para o usuário logado
    if request.user.is_authenticated:
        context.update({
            'total_farmacias': Farmacia.objects.count(),
            'total_medicamentos': Medicamento.objects.count(),
            'total_precos': Preco.objects.count(),
        })

    context.update(dados_formulario)
    return render(request, 'base/index.html', context)


def index(request):
    return renderizar_index(request)


def destino_seguro(request, destino):
    """Retorna o endereço de destino após o login somente se for uma página
    deste site (evita redirecionar o usuário para sites de terceiros)"""
    if destino and url_has_allowed_host_and_scheme(
            destino, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return destino
    return None


# VIEW DE LOGIN
def login_view(request):
    if request.method == 'POST':
        usuario_inserido = request.POST.get('username')
        senha_inserida = request.POST.get('password')
        # Página que o usuário tentou abrir antes de entrar
        proxima_pagina = request.POST.get('next', '')

        # O Django valida automaticamente a criptografia da senha
        user = authenticate(
            request, username=usuario_inserido, password=senha_inserida)

        if user is not None:
            login(request, user)
            messages.success(request, f'Bem-vindo de volta, {user.username}!')
            # Volta para a página que o usuário queria abrir ou, se não
            # houver, para a página principal
            return redirect(
                destino_seguro(request, proxima_pagina) or 'base:index')
        else:
            messages.error(request, 'Usuário ou senha incorretos.')
            # Reabre o modal de login com o usuário já preenchido
            return renderizar_index(
                request, aba_modal='login',
                dados_login={'username': usuario_inserido},
                next=destino_seguro(request, proxima_pagina) or '')

    return redirect('base:index')


# VIEW DE CADASTRO
def register(request):
    if request.method == 'POST':
        usuario_inserido = request.POST.get('username', '').strip()
        email_inserido = request.POST.get('email', '').strip()
        senha_inserida = request.POST.get('password', '')

        # Em caso de erro, reabre o modal de cadastro com usuário e e-mail
        # preenchidos (a senha nunca é devolvida para a página)
        def devolver_cadastro():
            return renderizar_index(
                request, aba_modal='register',
                dados_cadastro={
                    'username': usuario_inserido, 'email': email_inserido})

        # Todos os campos são obrigatórios
        if not usuario_inserido or not email_inserido or not senha_inserida:
            messages.error(request, 'Preencha usuário, e-mail e senha.')
            return devolver_cadastro()

        # Validação básica: verificar se o usuário já existe
        if User.objects.filter(username=usuario_inserido).exists():
            messages.error(request, 'Este nome de usuário já existe.')
            return devolver_cadastro()

        # Validação básica: verificar se o e-mail já existe
        if User.objects.filter(email=email_inserido).exists():
            messages.error(request, 'Este e-mail já está cadastrado.')
            return devolver_cadastro()

        # Valida o formato do usuário e do e-mail e a força da senha
        # (regras do AUTH_PASSWORD_VALIDATORS no settings.py)
        novo_usuario = User(username=usuario_inserido, email=email_inserido)
        try:
            novo_usuario.full_clean(exclude=['password'])
            validate_password(senha_inserida, user=novo_usuario)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
            return devolver_cadastro()

        # Criando o usuário com a senha criptografada de forma segura
        user = User.objects.create_user(
            username=usuario_inserido,
            email=email_inserido,
            password=senha_inserida
        )
        user.save()

        # Loga o usuário automaticamente após o cadastro bem-sucedido
        login(request, user)
        messages.success(
            request, 'Conta criada com sucesso! Você já está logado.')
        return redirect('base:index')

    return redirect('base:index')

# VIEW DE LOGOUT


# Logout só por POST: um link de outro site não consegue deslogar
@require_POST
def logout_view(request):
    logout(request)  # Remove a sessão do usuário do navegador de forma segura
    messages.success(request, 'Você saiu da sua conta com sucesso.')
    return redirect('base:index')
