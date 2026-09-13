from django.urls import path

from . import views


app_name = 'preco'

urlpatterns = [
    path('', views.cadastrar, name='cadastrar'),
    path('listar/', views.listar, name='listar'),
    path('atualizar/<int:id>', views.atualizar, name='atualizar'),
    path('deletar/<int:id>', views.deletar, name='deletar'),
]
