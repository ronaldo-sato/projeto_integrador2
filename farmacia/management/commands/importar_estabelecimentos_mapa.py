"""Importa os estabelecimentos registrados no MAPA para produtos veterinários.

Uso:
    python manage.py importar_estabelecimentos_mapa
    python manage.py importar_estabelecimentos_mapa --arquivo produto_veterinario.csv

Baixa o CSV "Produto Veterinário" do portal de dados abertos do MAPA
(atualizado semanalmente) e substitui a tabela de estabelecimentos. Pode ser
executado de novo a qualquer momento para atualizar.
"""
from pathlib import Path
from urllib.error import URLError

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from farmacia import mapa
from farmacia.models import EstabelecimentoMapa


class Command(BaseCommand):
    help = 'Importa os estabelecimentos registrados no MAPA (produtos veterinários)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--arquivo', help='Usa um CSV já baixado em vez de baixar do MAPA')

    def handle(self, *args, **opcoes):
        if opcoes.get('arquivo'):
            conteudo = Path(opcoes['arquivo']).read_bytes()
        else:
            try:
                self.stdout.write('Consultando o portal de dados abertos do MAPA...')
                url = mapa.url_do_csv()
                self.stdout.write(f'Baixando {url}')
                conteudo = mapa.baixar(url)
            except (URLError, TimeoutError, OSError, LookupError, ValueError, KeyError) as erro:
                raise CommandError(f'Não foi possível baixar os dados do MAPA: {erro}')

        estabelecimentos = mapa.ler_estabelecimentos(conteudo)
        if not estabelecimentos:
            raise CommandError('Nenhum estabelecimento encontrado no arquivo.')

        # Substitui a tabela inteira de uma vez (se algo falhar, os dados
        # anteriores continuam intactos)
        with transaction.atomic():
            EstabelecimentoMapa.objects.all().delete()
            EstabelecimentoMapa.objects.bulk_create(
                (EstabelecimentoMapa(**dados) for dados in estabelecimentos.values()),
                batch_size=2000)

        ativos = sum(e['situacao'] == 'ativo' for e in estabelecimentos.values())
        self.stdout.write(self.style.SUCCESS(
            f'{len(estabelecimentos)} estabelecimentos importados ({ativos} ativos).'))
