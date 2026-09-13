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
