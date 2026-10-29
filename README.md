# projeto_integrador2

Esta aplicação foi desenvolvida no contexto da disciplica **DRP03 - Projeto Integrador em Computação 2 da Univesp**, cujo tema **"Desenvolver um software com framework web que utilize banco de dados, inclua script web (Javascript), nuvem, uso de API, acessibilidade, controle de versão e testes. Opcionalmente, incluir análise de dados"**, visa promover uma solução para algum problema na comunidade. Além disso, é uma continuação da aplicação desenvolvida na disciplina Projeto Integrador 1.

**Comparador Vet**: comparador de preços de medicamentos veterinários em farmácias, pet shops, agropecuárias e clínicas.

## Stack

- **Backend:** Python 3.12 + Django 6.0
- **Banco de dados:** PostgreSQL
- **Frontend:** templates do Django + Bootstrap 5 + JavaScript
- **APIs externas:** ViaCEP e BrasilAPI (CEP e CNPJ) e dados abertos do MAPA (produtos e estabelecimentos veterinários)
- **Deploy:** Render (aplicação) + Neon (banco)

## Como rodar localmente

Pré-requisitos: [Python 3.12](https://www.python.org/downloads/), [PostgreSQL](https://www.postgresql.org/download/) e [Git](https://git-scm.com/).

**1. Clonar o projeto**

```bash
git clone https://github.com/ronaldo-sato/projeto_integrador2.git
cd projeto_integrador2
```

**2. Instalar as dependências**

Com conda:

```bash
conda create --name projeto_integrador2 --file requirements.txt -c conda-forge
conda activate projeto_integrador2
```

Ou com venv (Windows):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install "django>=6.0.8,<6.1" "psycopg[binary]" python-dotenv
```

**3. Criar o banco**

Abra o `psql` como superusuário (`psql -U postgres`), troque a senha e execute:

```sql
CREATE ROLE projeto_integrador LOGIN CREATEDB PASSWORD 'sua_senha_aqui';
CREATE DATABASE projeto_integrador2 OWNER projeto_integrador;
```

**4. Configurar a conexão**

Copie o arquivo `.env.example` para `.env` e coloque a senha do passo anterior em `DB_PASSWORD`:

```bash
copy .env.example .env
```

**5. Criar as tabelas e importar os dados do MAPA** (precisa de internet, leva alguns minutos)

```bash
python manage.py migrate
python manage.py importar_estabelecimentos_mapa
python manage.py importar_produtos_mapa
```

**6. Rodar**

```bash
python manage.py runserver
```

Acesse http://127.0.0.1:8000/ e crie uma conta.

**Testes:** `python manage.py test`
