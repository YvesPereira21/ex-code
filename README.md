# ex-code 🚀

> **Ferramenta CLI para automação de scaffolding e manutenção cirúrgica de projetos backend em FastAPI e Spring Boot.**

O **ex-code** é uma ferramenta de linha de comando desenvolvida em Python para acelerar o ciclo de vida inicial e evolutivo de backends. Em vez de criar manualmente dezenas de arquivos, classes, schemas, repositórios, migrações e relacionamentos repetitivos, o desenvolvedor responde a um assistente interativo no terminal e obtém um projeto pronto, padronizado e funcional.

Além da geração inicial (*scaffolding*), o **ex-code** possui um módulo inovador de **Edição Cirúrgica**, permitindo adicionar novas entidades, campos, relacionamentos e DTOs a projetos existentes sem sobrescrever regras de negócio, métodos customizados ou comentários já existentes.

---

## 🌟 Principais Recursos

- ⚡ **Dois Frameworks de Mercado:**
  - **FastAPI**: SQLAlchemy 2.0 assíncrono (`Mapped[...]`, `mapped_column`), Pydantic v2 para validação, suporte a migrações com Alembic e gerenciamento com Poetry.
  - **Spring Boot**: Java 21, Maven, Spring Data JPA com UUID, Java Records para DTOs, mappers MapStruct e anotações Lombok.
- 🏛️ **Duas Arquiteturas de Diretórios:**
  - **Em Camadas (Layered)**: separação clássica por responsabilidades (`models/`, `schemas/`, `routers/`, `controllers/`, etc.).
  - **Por Domínio (Domain-Driven)**: agrupamento coeso por contextos e funcionalidades (`modules/<feature>/` ou `domain/<feature>/`).
- 🗄️ **Suporte a Múltiplos Bancos de Dados:**
  - PostgreSQL, MySQL, SQLite e H2.
- 🔑 **Convenções Inteligentes de Chave Primária:**
  - Geração automática de identificador UUID com convenções idiomáticas: `<entidade>_id` em *snake_case* para FastAPI e `<entidade>Id` em *camelCase* para Spring Boot (ambos mapeando para coluna `<entidade>_id` no banco).
- 🔄 **Relacionamentos Completos:**
  - Suporte intuitivo a `OneToOne`, `OneToMany`, `ManyToOne` e `ManyToMany`, com configuração de bidirecionalidade e geração de tabelas associativas/chaves estrangeiras.
- 🔬 **Modificação Cirúrgica sem Regressão:**
  - Uso de **LibCST** (Concrete Syntax Tree) para Python e modificadores dedicados para Java, garantindo que código manual, docstrings e formatações anteriores nunca sejam perdidos.
- 🎨 **Visualização de Diff no Terminal:**
  - Pré-visualização de todas as linhas adicionadas e modificadas com destaque de sintaxe antes de qualquer alteração ser gravada no disco.
- 🛡️ **Segurança e Backups Automáticos:**
  - Criação automática de snapshots com data/hora em `.excode/backups/<timestamp>/` antes de qualquer alteração cirúrgica.
  - Manifesto leve `.excode.json` para histórico e integridade do projeto.

---

## 📋 Pré-requisitos

- **Python 3.12** ou superior
- **Poetry** (Gerenciador de dependências Python):
  ```bash
  pip install poetry
  ```
- **Git**
- *(Opcional para executar projetos Spring Boot)*: **Java 21 JDK** e **Maven**

---

## 📦 Instalação

Clone o repositório e instale as dependências com o Poetry:

```bash
git clone https://github.com/YvesPereira21/ex-code.git
cd ex-code
poetry install
```

---

## 🖥️ Como Executar

Você pode iniciar o **ex-code** diretamente pelo atalho registrado no Poetry:

```bash
poetry run ex-code
```

Ou através do módulo Python:

```bash
poetry run python -m ex_code
```

Ao iniciar, você verá o banner de boas-vindas e o menu principal:

```text
  ███████╗██╗  ██╗      ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗██╔╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝
  █████╗   ╚███╔╝█████╗██║     ██║   ██║██║  ██║█████╗  
  ██╔══╝   ██╔██╗╚════╝██║     ██║   ██║██║  ██║██╔══╝  
  ███████╗██╔╝ ██╗     ╚██████╗╚██████╔╝██████╔╝███████╗
  ╚══════╝╚═╝  ╚═╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝

? O que você deseja fazer? (Use arrow keys)
 » ✨  Criar novo projeto
   🔧  Editar projeto existente
   🚪  Sair
```

---

## 📖 Guia de Uso

### 1. Criando um Novo Projeto (`✨ Criar novo projeto`)

O assistente guiará você por 6 etapas simples:

1. **Informações Básicas:**
   - Diretório de destino onde o projeto será criado.
   - Nome do projeto e descrição.
   - Framework backend desejado (**FastAPI** ou **Spring Boot**).
2. **Entidades e Atributos:**
   - Adicione quantas entidades precisar (ex: `User`, `Product`, `Order`).
   - Para cada entidade, defina seus campos com tipos universais (`String`, `Integer`, `Float`, `Boolean`, `DateTime`, `UUID`, etc.).
   - Defina se o campo pode ser nulo (`nullable`) ou único (`unique`).
   - A chave primária UUID é configurada automaticamente segundo os padrões da linguagem escolhida.
3. **Relacionamentos:**
   - Conecte suas entidades selecionando a origem, o destino e a cardinalidade (`1:1`, `1:N`, `N:1`, `N:N`).
   - Defina se o relacionamento deve ser bidirecional.
4. **Schemas e DTOs:**
   - Crie DTOs / Schemas específicos selecionando campos derivados de entidades existentes ou adicionando campos próprios.
5. **Arquitetura e Banco de Dados:**
   - Escolha entre arquitetura **Em Camadas** ou **Por Domínio**.
   - Escolha o banco de dados (**PostgreSQL**, **MySQL**, **SQLite** ou **H2**).
   - Para Spring Boot, defina o pacote Java base (ex: `com.meuapp.api`).
6. **Confirmação e Geração:**
   - Uma tabela com o resumo completo de entidades, campos e configurações é renderizada no terminal.
   - Após sua confirmação, o projeto completo é gerado no disco pronto para ser executado.

---

### 2. Editando um Projeto Existente (`🔧 Editar projeto existente`)

O modo de edição inspeciona qualquer projeto previamente gerado pelo **ex-code** (ou projetos que possuam a estrutura reconhecida):

1. **Inspeção do Projeto:**
   - Informe a pasta do projeto existente. A CLI detecta o framework, a arquitetura e carrega todas as entidades e DTOs existentes.
2. **Menu de Modificações:**
   - `Adicionar nova entidade`: cria o novo modelo/entidade e gera os schemas/DTOs e repositórios correspondentes.
   - `Adicionar campo a entidade existente`: insere novas colunas na classe sem apagar código existente.
   - `Adicionar relacionamento entre entidades`: atualiza ambos os arquivos envolvidos de forma consistente.
   - `Adicionar novo DTO / Schema`: adiciona novos Schemas Pydantic ou Records Java.
   - `Adicionar campo a DTO existente`: atualiza a definição de dados.
3. **Pré-visualização do Diff & Confirmação:**
   - Antes de aplicar, o **ex-code** exibe um painel de **Diff Colorido** mostrando exatamente quais linhas serão inseridas ou modificadas.
   - É gerado um backup de segurança em `.excode/backups/<timestamp>/`.
   - As alterações são aplicadas de maneira cirúrgica e o `.excode.json` é sincronizado.

---

## 🏗️ Estrutura dos Projetos Gerados

### FastAPI

#### Arquitetura em Camadas (Layered)
```text
meu-projeto-fastapi/
├── app/
│   ├── api/
│   │   └── routers/
│   │       ├── user_router.py
│   │       └── order_router.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   ├── user.py
│   │   └── order.py
│   ├── schemas/
│   │   ├── user.py
│   │   └── order.py
│   └── main.py
├── alembic/
│   ├── env.py
│   └── script.py.mako
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── .excode.json
```

#### Arquitetura por Domínio (Domain-Driven)
```text
meu-projeto-fastapi/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── modules/
│   │   ├── user/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   └── router.py
│   │   └── order/
│   │       ├── models.py
│   │       ├── schemas.py
│   │       └── router.py
│   └── main.py
├── pyproject.toml
└── .excode.json
```

---

### Spring Boot

#### Arquitetura em Camadas (Layered)
```text
meu-projeto-springboot/
├── pom.xml
├── src/
│   └── main/
│       ├── java/com/exemplo/app/
│       │   ├── Application.java
│       │   ├── controller/
│       │   ├── dto/
│       │   ├── mapper/
│       │   ├── model/
│       │   ├── repository/
│       │   └── service/
│       └── resources/
│           └── application.properties
└── .excode.json
```

---

## 🧪 Testes Automatizados

O projeto conta com suíte completa de testes unitários e de integração utilizando `pytest`:

```bash
# Executar todos os testes
poetry run pytest

# Executar com relatório detalhado
poetry run pytest -v

# Verificar padrões e qualidade de código com o Ruff
poetry run ruff check .
poetry run ruff format --check .
```

---

## 📄 Licença

Este projeto é distribuído sob a licença MIT. Sinta-se livre para utilizar, contribuir e customizar conforme suas necessidades.
