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
]
