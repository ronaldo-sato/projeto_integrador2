"""Importa o catálogo de produtos veterinários registrados no MAPA.

Uso:
    python manage.py importar_produtos_mapa
    python manage.py importar_produtos_mapa --pasta C:\\mapa   (guarda as planilhas)

Baixa as planilhas oficiais publicadas pelo MAPA (ver medicamento/mapa.py),
junta os eventos em ordem cronológica (um cancelamento posterior tira o
produto do catálogo; um novo registro o traz de volta) e substitui o
catálogo no banco. Pode ser executado de novo a qualquer momento para
atualizar com as planilhas mais recentes.
"""
import hashlib
import time
from pathlib import Path
from urllib.error import URLError

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from medicamento import mapa
from medicamento.models import ProdutoMapa

# Pausa entre downloads, para não sobrecarregar o site do governo
PAUSA_ENTRE_DOWNLOADS = 0.5


class Command(BaseCommand):
    help = 'Importa o catálogo de produtos veterinários registrados no MAPA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pasta',
            help='Pasta para guardar as planilhas baixadas (reaproveitadas '
                 'nas próximas execuções)')

    def handle(self, *args, **opcoes):
        pasta = Path(opcoes['pasta']) if opcoes.get('pasta') else None
        if pasta:
            pasta.mkdir(parents=True, exist_ok=True)

        self.stdout.write('Consultando a página de listas do MAPA...')
        try:
            html = mapa.baixar(mapa.PAGINA_LISTAS).decode('utf-8', 'replace')
        except (URLError, TimeoutError, OSError) as erro:
            raise CommandError(f'Não foi possível acessar o site do MAPA: {erro}')

        links = sorted(mapa.descobrir_planilhas(html), key=mapa.chave_cronologica)
        if not links:
            raise CommandError(
                'Nenhuma planilha encontrada. A página do MAPA pode ter mudado.')
        self.stdout.write(f'{len(links)} planilhas encontradas.')

        # Junta os eventos em ordem cronológica: o último sobre cada produto vale
        catalogo = {}
        for numero, link in enumerate(links, start=1):
            nome_arquivo = link.rsplit('/', 1)[-1]
            try:
                conteudo = self._obter(link, pasta)
            except (URLError, TimeoutError, OSError) as erro:
                self.stderr.write(f'  [{numero}] falhou ao baixar {nome_arquivo}: {erro}')
                continue

            eventos = mapa.extrair_eventos(mapa.ler_planilha(conteudo), origem=link)
            for evento in eventos:
                chave = f'{mapa.normalizar(evento.nome)}|{mapa.chave_empresa(evento.empresa)}'
                anterior = catalogo.get(chave)
                # Planilhas de aprovação não trazem natureza/controle: mantém o
                # que já se sabia sobre o produto
                if anterior:
                    evento.natureza = evento.natureza or anterior.natureza
                    evento.registro = evento.registro or anterior.registro
                    if evento.animais_producao is None:
                        evento.animais_producao = anterior.animais_producao
                    if evento.controle_especial is None:
                        evento.controle_especial = anterior.controle_especial
                catalogo[chave] = evento
            self.stdout.write(f'  [{numero}/{len(links)}] {len(eventos):5d} eventos  {nome_arquivo[:70]}')

        if not catalogo:
            raise CommandError('Nenhum produto encontrado nas planilhas.')

        produtos = [
            ProdutoMapa(
                chave=chave[:300], nome=evento.nome[:255],
                empresa=evento.empresa[:255], situacao=evento.situacao,
                natureza=evento.natureza, registro=evento.registro,
                animais_producao=evento.animais_producao,
                controle_especial=evento.controle_especial)
            for chave, evento in catalogo.items()]

        # Substitui o catálogo inteiro de uma vez (se algo falhar, o
        # catálogo anterior continua intacto)
        with transaction.atomic():
            ProdutoMapa.objects.all().delete()
            ProdutoMapa.objects.bulk_create(produtos, batch_size=1000)

        ativos = sum(p.situacao != ProdutoMapa.Situacao.CANCELADO for p in produtos)
        self.stdout.write(self.style.SUCCESS(
            f'Catálogo atualizado: {len(produtos)} produtos '
            f'({ativos} ativos, {len(produtos) - ativos} cancelados).'))

    def _obter(self, link, pasta):
        """Baixa a planilha (ou reaproveita a cópia guardada na pasta)"""
        if pasta:
            # Nome estável a partir do link (o hash() do Python muda a cada execução)
            arquivo = pasta / f'planilha_{hashlib.sha1(link.encode()).hexdigest()[:12]}'
            if arquivo.exists():
                return arquivo.read_bytes()
        conteudo = mapa.baixar(mapa.url_de_download(link))
        time.sleep(PAUSA_ENTRE_DOWNLOADS)
        if pasta:
            arquivo.write_bytes(conteudo)
        return conteudo
