from django.shortcuts import render

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
        'titulo': 'Projeto Integrador 1',
    }
    return render(request, 'base/index.html', context)
