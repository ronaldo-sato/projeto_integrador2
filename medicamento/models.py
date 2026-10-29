from django.db import models

# Create your models here.


class Medicamento(models.Model):
    nome = models.CharField('Nome', max_length=100)
    fabricante = models.CharField('Fabricante', max_length=100)
    # Não necessita usar chave estrangeira, porque qualquer medicamento
    # existirá independente da farmácia.

    # Pode haver medicamento com mesmo nome,
    # desde que o fabricante seja diferente
    class Meta:
        unique_together = ('nome', 'fabricante')

    def __str__(self):
        return f'{self.nome} {self.fabricante}'


# Catálogo de produtos veterinários registrados no MAPA, montado a partir das
# planilhas oficiais (ver mapa.py e o comando importar_produtos_mapa). Serve
# para sugerir nomes no cadastro de medicamentos; não substitui o cadastro
class ProdutoMapa(models.Model):

    class Situacao(models.TextChoices):
        REGISTRADO = 'registrado', 'Registrado'
        LICENCA_PROVISORIA = 'licenca_provisoria', 'Licença provisória'
        CANCELADO = 'cancelado', 'Cancelado'

    class Natureza(models.TextChoices):
        FARMACEUTICO = 'farmaceutico', 'Farmacêutico'
        BIOLOGICO = 'biologico', 'Biológico'
        NAO_INFORMADA = '', 'Não informada'

    nome = models.CharField('Nome do produto', max_length=255)
    empresa = models.CharField('Empresa', max_length=255, blank=True)
    situacao = models.CharField(
        'Situação', max_length=20, choices=Situacao.choices)
    natureza = models.CharField(
        'Natureza', max_length=20, choices=Natureza.choices, blank=True)
    registro = models.CharField('Nº do registro/licença', max_length=60, blank=True)
    animais_producao = models.BooleanField(
        'Destinado a animais de produção', null=True)
    controle_especial = models.BooleanField('Controle especial', null=True)
    # Chave para identificar o mesmo produto escrito de formas diferentes
    chave = models.CharField(max_length=300, unique=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'produto do MAPA'
        verbose_name_plural = 'produtos do MAPA'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.empresa})'
