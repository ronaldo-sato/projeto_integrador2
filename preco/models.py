from django.db import models

from farmacia.models import Farmacia
from medicamento.models import Medicamento

# Create your models here.


class Preco(models.Model):
    # Relacionamento Muitos para Muitos:
    # O preço é de um medicamento em uma farmácia
    # Tabela preço faz essa associação
    # Chaves Estrangeiras (garante que não poderá ser cadastrado um
    # preço para farmácia ou medicamento que não existam):
    farmacia = models.ForeignKey(Farmacia, on_delete=models.CASCADE)
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE)

    preco = models.DecimalField(max_digits=8, decimal_places=2)
    # Registro do momento de inserção
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Garante que não haja preços diferentes para o mesmo
        # medicamento na mesma farmácia
        # unique_together = ('medicamento', 'farmacia')  # não guarda histórico

        # Ordena do mais novo para mais antigo
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.medicamento}: R${self.preco} ({self.data_hora})' + \
            f' em {self.farmacia}'
