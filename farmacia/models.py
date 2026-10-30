from urllib.parse import quote_plus

from django.db import models

# Create your models here.

# O nome das tabelas no Django seguem o padrão app_model

# Unidades federativas, para o campo UF do endereço
UFS = [
    'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS',
    'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC',
    'SE', 'SP', 'TO',
]


# Representa qualquer estabelecimento que vende medicamentos veterinários
# (o nome "Farmacia" foi mantido para não alterar o restante do sistema)
class Farmacia(models.Model):

    class Tipo(models.TextChoices):
        FARMACIA = 'farmacia', 'Farmácia'
        PETSHOP = 'petshop', 'Pet shop'
        AGROPECUARIA = 'agropecuaria', 'Agropecuária'
        CLINICA = 'clinica', 'Clínica veterinária'

    # O nome pode se repetir: uma mesma rede pode ter várias unidades
    nome = models.CharField('Nome', max_length=100)
    tipo = models.CharField(
        'Tipo', max_length=20, choices=Tipo.choices, default=Tipo.FARMACIA)

    # Partes do endereço (preenchidas com a ajuda da busca por CEP)
    cep = models.CharField('CEP', max_length=9, blank=True, default='')
    logradouro = models.CharField(
        'Logradouro', max_length=150, blank=True, default='')
    numero = models.CharField('Número', max_length=20, blank=True, default='')
    complemento = models.CharField(
        'Complemento', max_length=60, blank=True, default='')
    bairro = models.CharField('Bairro', max_length=80, blank=True, default='')
    cidade = models.CharField('Cidade', max_length=80, blank=True, default='')
    uf = models.CharField('UF', max_length=2, blank=True, default='')

    # Endereço completo em uma linha, montado a partir das partes acima.
    # É o que aparece nas listas e na pesquisa
    endereco = models.CharField('Endereço', max_length=255)

    # CNPJ (opcional, só os 14 dígitos): permite preencher o cadastro pela
    # Receita Federal e indicar se o estabelecimento é registrado no MAPA
    cnpj = models.CharField('CNPJ', max_length=14, blank=True, default='')

    # Podem farmácias com mesmo nome desde que com endereço diferente
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['nome', 'endereco'],
                name='unique_farmacia_endereco'
            ),
            # Cada CNPJ é uma unidade: não pode ser cadastrado duas vezes
            # (vários estabelecimentos sem CNPJ continuam permitidos)
            models.UniqueConstraint(
                fields=['cnpj'],
                condition=~models.Q(cnpj=''),
                name='unique_farmacia_cnpj'
            ),
        ]

    def __str__(self):
        return f'{self.nome} {self.endereco}'

    @property
    def cnpj_formatado(self):
        """'49475833000106' -> '49.475.833/0001-06'"""
        c = self.cnpj
        return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}' if len(c) == 14 else c

    @property
    def nome_com_local(self):
        """Nome com o bairro (ou o endereço), para diferenciar unidades da
        mesma rede nas listas de seleção"""
        return f'{self.nome} - {self.bairro or self.endereco}'

    @property
    def busca_google_maps(self):
        """Texto procurado no Google Maps: nome + endereço, para abrir o
        próprio estabelecimento (e não só a rua) quando o Google o conhece"""
        return f'{self.nome}, {self.endereco}'

    @property
    def link_google_maps(self):
        """Link que abre o estabelecimento no Google Maps (site ou app).
        Não usa chave nem tem custo"""
        return ('https://www.google.com/maps/search/?api=1&query='
                + quote_plus(self.busca_google_maps))


def montar_endereco(logradouro, numero, complemento, bairro, cidade, uf):
    """Monta o endereço completo em uma linha.
    Ex.: 'Rua das Flores, 87 - Sala 2 - Vila Nova, São Paulo/SP'"""
    endereco = f'{logradouro}, {numero}'
    if complemento:
        endereco += f' - {complemento}'
    return f'{endereco} - {bairro}, {cidade}/{uf}'


# Estabelecimentos registrados no MAPA para comercializar, fabricar ou
# manipular produtos veterinários. Vem do CSV de dados abertos do SIPEAGRO
# (comando importar_estabelecimentos_mapa), atualizado semanalmente pelo MAPA
class EstabelecimentoMapa(models.Model):

    class Situacao(models.TextChoices):
        ATIVO = 'ativo', 'Ativo'
        SUSPENSO = 'suspenso', 'Suspenso'
        CANCELADO = 'cancelado', 'Cancelado'

    cnpj = models.CharField('CNPJ', max_length=14, unique=True)
    registro = models.CharField('Nº do registro no MAPA', max_length=20, blank=True)
    razao_social = models.CharField('Razão social', max_length=255)
    nome_fantasia = models.CharField('Nome fantasia', max_length=255, blank=True)
    municipio = models.CharField('Município', max_length=100, blank=True)
    uf = models.CharField('UF', max_length=2, blank=True)
    situacao = models.CharField('Situação', max_length=20, choices=Situacao.choices)
    # Ex.: "COMERCIANTE, MANIPULADOR"
    atividades = models.CharField('Atividades', max_length=255, blank=True)
    # Ex.: "PRODUTO FARMACÊUTICO, PRODUTO BIOLÓGICO"
    classificacoes = models.CharField('Classificações', max_length=255, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'estabelecimento do MAPA'
        verbose_name_plural = 'estabelecimentos do MAPA'

    def __str__(self):
        return f'{self.nome} ({self.municipio}/{self.uf})'

    @property
    def nome(self):
        """Nome fantasia ou, se não houver, a razão social"""
        return self.nome_fantasia or self.razao_social

    @property
    def vende_ao_publico(self):
        return any(a in self.atividades for a in ('COMERCIANTE', 'MANIPULADOR'))
