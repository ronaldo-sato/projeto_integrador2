from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

from farmacia.models import Farmacia
from medicamento.models import Medicamento

# Create your views here.


# def index(request):
#     return render(
#         request,
#         'base/index.html')


# Ter as farmácias e medicamentos cadastrados para usá-los nos selects
# do forms de cadastro de preço
def index(request):

    # Incluindo medicamentos_unicos: nome de medicamentos sem repetição
    farmacias = Farmacia.objects.all()
    medicamentos = Medicamento.objects.all()
    medicamentos_unicos = Medicamento.objects.values('nome') \
        .distinct().order_by('nome')

    # Para manutenção de estado de formulário (após selecionar
    # medicamento, "filtrar marcas")
    fabricantes_filtrados = None
    # Captura medicamento do select enviado pela url
    medicamento_selecionado = request.GET.get('medicamento_filtro')

    # Para manter o estado após o filtro
    if medicamento_selecionado:

        fabricantes_filtrados = Medicamento.objects.filter(
            nome__iexact=medicamento_selecionado.strip())

    context = {
        'farmacias': farmacias,
        'medicamentos': medicamentos,
        'medicamentos_unicos': medicamentos_unicos,
        'medicamento_selecionado': medicamento_selecionado,
        'fabricantes_filtrados': fabricantes_filtrados,
        'titulo': 'Projeto Integrador 2',
    }
    return render(request, 'base/index.html', context)


# VIEW DE LOGIN
def login_view(request):
    if request.method == 'POST':
        usuario_inserido = request.POST.get('username')
        senha_inserida = request.POST.get('password')

        # O Django valida automaticamente a criptografia da senha
        user = authenticate(
            request, username=usuario_inserido, password=senha_inserida)

        if user is not None:
            login(request, user)
            messages.success(request, f'Bem-vindo de volta, {user.username}!')
            # Redireciona para a página principal após logar
            return redirect('base:index')
        else:
            messages.error(request, 'Usuário ou senha incorretos.')
            return redirect('base:index')

    return redirect('base:index')


# VIEW DE CADASTRO
def register(request):
    if request.method == 'POST':
        usuario_inserido = request.POST.get('username')
        email_inserido = request.POST.get('email')
        senha_inserida = request.POST.get('password')

        # Validação básica: verificar se o usuário já existe
        if User.objects.filter(username=usuario_inserido).exists():
            messages.error(request, 'Este nome de usuário já existe.')
            return redirect('base:index')

        # Validação básica: verificar se o e-mail já existe
        if User.objects.filter(email=email_inserido).exists():
            messages.error(request, 'Este e-mail já está cadastrado.')
            return redirect('base:index')

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


def logout_view(request):
    logout(request)  # Remove a sessão do usuário do navegador de forma segura
    messages.success(request, 'Você saiu da sua conta com sucesso.')
    return redirect('base:index')
