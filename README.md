# OrbisHealth — v1 (estrutura + login)

Sistema de gerenciamento de emergências médicas (SAMU-like). Esta etapa entrega
apenas: estrutura do projeto, conexão com o banco, models principais e o fluxo
de login (HU-001) de ponta a ponta.

## Stack

- Backend: Python + Flask (padrão MVC)
- ORM: SQLAlchemy + Flask-Migrate (Alembic)
- Banco: PostgreSQL
- Autenticação: Flask-Login (sessão) + bcrypt
- Frontend: HTML + CSS + JS puro, via Jinja2

## Pré-requisitos

- Python 3.10+
- PostgreSQL rodando localmente, com o banco `orbis_health` já criado
  (pode criar pelo pgAdmin ou `createdb orbis_health`)

## Como rodar

Todos os comandos abaixo assumem que você está dentro da pasta `backend/`.

```bash
cd backend
```

### 1. Criar e ativar o virtualenv

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar o `.env`

```bash
cp .env.example .env
```

Edite o `.env` com os dados do seu PostgreSQL local:

```
SECRET_KEY=alguma-chave-aleatoria
DB_HOST=localhost
DB_PORT=5432
DB_NAME=orbis_health
DB_USER=postgres
DB_PASSWORD=sua-senha
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```

### 4. Rodar as migrations

Na primeira vez, é preciso inicializar o Flask-Migrate:

```bash
export FLASK_APP=run.py     # Windows (PowerShell): $env:FLASK_APP="run.py"
flask db init
flask db migrate -m "cria tabelas usuario, hospital e socorrista"
flask db upgrade
```

Isso cria as tabelas `usuario`, `hospital` e `socorrista` no banco `orbis_health`.

Em máquinas onde a pasta `migrations/` já existir (ex: você clonou o repo depois
de outra pessoa já ter rodado `flask db init`), pule o `flask db init` e rode
apenas `flask db upgrade` (e `flask db migrate` quando houver mudança nos models).

### 5. Rodar o seed do usuário admin

Não existe autocadastro (RN-012). Para ter um usuário para testar o login:

```bash
python seed.py
```

Isso cria o usuário admin de teste:

- **email:** `admin@orbishealth.com`
- **senha:** `Admin@123`

### 6. Rodar o servidor

```bash
python run.py
```

O projeto usa Flask-SocketIO (rastreamento em tempo real e chat), então o
`run.py` inicia o servidor via `socketio.run()` em vez do `flask run` padrão.
Lembre-se de ativar o virtualenv antes (`source venv/bin/activate`) — se
esquecer, o comando `flask`/`python` do sistema é usado no lugar do de
dentro do `venv/`, e as dependências do projeto (Flask-Login etc.) não são
encontradas.

Acesse `http://127.0.0.1:5000` — a rota raiz redireciona para `/login`.

## Fluxo de login (HU-001) implementado

- **Sucesso:** mensagem "Login com Sucesso!" e redirecionamento para
  `/dashboard`, que mostra "Dashboard {papel}".
- **Credenciais inválidas:** mensagem "E-mail ou senha incorretos!" e
  incremento de `tentativas_falhas`.
- **Bloqueio por tentativas:** após 5 tentativas incorretas seguidas
  (configurável via `MAX_LOGIN_ATTEMPTS`), o login fica bloqueado por 15
  minutos (configurável via `LOGIN_LOCKOUT_MINUTES`), mostrando "Perfil
  temporariamente bloqueado" mesmo com a senha certa, até o bloqueio expirar.
- **Logout:** mensagem "Usuário deslogado com sucesso!" e volta para o login.

Regras adicionais:

- RN-001: `papel` é obrigatório (enum `socorrista`/`hospital`/`admin`).
- RN-012: não há rota de cadastro; usuários só são criados via `seed.py`.
- RN-014: socorrista com `Usuario.ativo = False` consegue logar normalmente
  (isso será usado para bloquear ações operacionais em etapas futuras).
- RN-015: usuário do papel `hospital` vinculado a um `Hospital.ativo = False`
  tem o login bloqueado.

## Fora de escopo nesta etapa

Cadastro de hospitais/socorristas via tela, CRUD de ocorrências, chat, mapa,
JWT — tudo isso fica para etapas futuras.
