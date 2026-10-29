from django.urls import path

from . import views

app_name = 'farmacia'

# redirect procura uma rota, a rota aponta para uma função, a view faz
# o que tiver que fazer e renderiza um template

urlpatterns = [
    path('', views.cadastrar, name='cadastrar'),
    path('listar/', views.listar, name='listar'),
    path('atualizar/<int:id>', views.atualizar, name='atualizar'),
    path('deletar/<int:id>', views.deletar, name='deletar'),
    # Consulta de endereço pelo CEP (usada pelo formulário via JavaScript)
    path('cep/<str:cep>/', views.buscar_cep, name='buscar_cep'),
    # Dados para preencher o cadastro pelo CNPJ (MAPA + Receita Federal)
    path('cnpj/<str:cnpj>/', views.buscar_cnpj, name='buscar_cnpj'),
    # Sugestões de estabelecimentos registrados no MAPA para o campo de nome
    path('sugestoes/', views.sugerir, name='sugestoes'),
]
