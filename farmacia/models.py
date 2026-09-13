from django.db import models

# Create your models here.

# O nome das tabelas no Django seguem o padrão app_model


class Farmacia(models.Model):

    nome = models.CharField('Nome', max_length=100, unique=True)
    endereco = models.CharField('Endereço', max_length=255)

    # Podem farmácias com mesmo nome desde que com endereço diferente
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['nome', 'endereco'],
                name='unique_farmacia_endereco'
            )
        ]

    def __str__(self):
        return f'{self.nome} {self.endereco}'
