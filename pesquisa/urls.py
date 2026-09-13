from django.urls import path

from . import views

app_name = 'pesquisa'

urlpatterns = [
    path('precos/', views.pesquisar, name='precos'),
]
