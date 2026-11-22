# OrbisHealth

Sistema de gerenciamento de emergências médicas (SAMU-like): ocorrência e
prontuário com fotos, escolha do hospital por leitos e estrutura, trajeto em
tempo real, painel do hospital, chat, histórico e administração com auditoria.

## Stack

- Backend: Python + Flask (padrão MVC)
- ORM: SQLAlchemy + Flask-Migrate (Alembic)
- Banco: PostgreSQL
- Autenticação: Flask-Login (sessão) + bcrypt
- Frontend: HTML + CSS + JS puro, via Jinja2

## Pré-requisitos

- Python 3.12 a 3.14 (testado em instalação limpa — ver Plano de Testes, 7.2.12)
- PostgreSQL rodando localmente, com o banco `orbis_health` já criado
  (pode criar pelo pgAdmin ou `createdb orbis_health`)
- Acesso à internet (mapas, fontes e busca de endereços vêm de fora)

Para instalar num servidor ou em outro computador, veja também
[Hospedar em outro computador](#hospedar-em-outro-computador).

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

A pasta `migrations/` já vem no repositório. **Não** rode `flask db init`
nem `flask db migrate` — só aplique as migrations:

```bash
export FLASK_APP=run.py     # Windows (PowerShell): $env:FLASK_APP="run.py"
flask db upgrade
```

### 5. Rodar o seed do usuário admin

Não existe autocadastro (RN-012). Para ter um usuário para testar o login:

```bash
python seed.py
```

Isso cria o usuário admin de teste:

- **email:** `admin@orbishealth.com`
- **senha:** `Admin@123`

Opcional — dados de demonstração de Brasília (44 hospitais públicos com pronto-socorro do DF e
Entorno, 20 socorristas, ocorrências e conversas; senha `Senha@123`):

```bash
python seed_demo.py
```

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

Para recarregar sozinho ao editar o código, coloque `FLASK_DEBUG=1` no `.env`
(o modo debug fica desligado por padrão: ele expõe um console que executa
código no servidor).

## Hospedar em outro computador

Roteiro testado numa instalação do zero (pasta copiada, virtualenv novo,
banco vazio). O computador que hospeda precisa de **internet**: os mapas,
as fontes, o Leaflet e o Socket.IO do navegador vêm de servidores externos,
e a busca de endereços e rotas usa o OpenStreetMap.

### 1. Levar o código

Leve a pasta do projeto **sem** `backend/venv/` (é recriado lá) e sem
`backend/.env` (crie um novo, passo 3). Pelo Git: `git clone` do
repositório — confira antes se tudo foi commitado e enviado (`git status`).

Siga então os passos 1 e 2 de "Como rodar" (virtualenv + `pip install`).

### 2. Levar os dados (opcional — só se quiser manter os cadastros atuais)

No computador **atual**:

```bash
pg_dump -h localhost -U postgres -Fc orbis_health > orbis_health.dump
```

Copie também a pasta `backend/uploads/` (fotos dos pacientes). No computador
**novo**, com o PostgreSQL instalado (versão igual ou mais nova que a do
atual):

```bash
createdb -h localhost -U postgres orbis_health
pg_restore -h localhost -U postgres -d orbis_health --no-owner orbis_health.dump
flask db upgrade        # aplica migrations que o dump ainda não tenha
```

e coloque a pasta `uploads/` copiada dentro de `backend/`, **no lugar** da
que existir lá. Confira que ficou `backend/uploads/anexos/...`: se o
sistema já tinha criado uma `uploads/` vazia, copiar por cima pode gerar
`backend/uploads/uploads/`, e as fotos somem das telas. Sem dados antigos,
pule este passo e use `flask db upgrade` + `python seed.py`.

> O dump e a pasta `uploads/` têm dados de pacientes: transfira por pendrive
> ou rede local, não por serviços públicos, e apague as cópias depois.

### 3. Criar o `.env`

Copie `.env.example` para `.env` e preencha. Gere uma `SECRET_KEY` nova:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Escolher como o sistema será acessado

| Acesso | `.env` | Observação |
|---|---|---|
| Só no próprio computador | `HOST=127.0.0.1` | Tudo funciona em `http://127.0.0.1:5000`. |
| Outros aparelhos da mesma rede | `HOST=0.0.0.0` | Abra a porta 5000 no firewall. Acesse por `http://IP-do-computador:5000`. |
| Pela internet, com HTTPS | `HOST=127.0.0.1` e `ATRAS_DE_PROXY=1` | Um proxy reverso com HTTPS (Caddy, nginx, Cloudflare Tunnel) recebe o acesso e repassa para `127.0.0.1:5000`. |

**Importante:** os navegadores só liberam a **localização do aparelho**
(usada pelo socorrista para abrir a ocorrência e enviar o trajeto) e o modo
offline em `https://` ou em `127.0.0.1`/`localhost`. Acessando por
`http://IP:5000`, o resto funciona, mas o socorrista no navegador não envia
a posição. Para isso, use HTTPS (terceira linha da tabela). O app mobile
(pasta `mobile/`) não tem essa limitação.

Com o proxy na frente, `ATRAS_DE_PROXY=1` é obrigatório: sem ele o login
pelo endereço `https://` é recusado (a proteção contra CSRF vê o endereço
como `http://`). Não ligue essa opção sem proxy.

Exemplo com Caddy (gera e renova o certificado HTTPS sozinho; o domínio
precisa apontar para o computador e as portas 80/443 precisam estar abertas):

```
orbis.seudominio.com.br {
    reverse_proxy 127.0.0.1:5000
}
```

### 5. Antes de deixar outras pessoas acessarem

- Troque a senha do admin (tela Perfil). As senhas de exemplo
  (`Admin@123`, `Senha@123`) estão publicadas neste README.
- Sem dados reais, prefira não rodar o `seed_demo.py` num servidor aberto.
- Mantenha `FLASK_DEBUG=0`.
- O servidor do `run.py` atende bem um grupo pequeno (demonstração, turma,
  equipe). Para uso real com muitos acessos simultâneos, troque por um
  servidor de produção (ex.: gunicorn com worker eventlet/gevent).

### Modo demonstração (apresentação do TCC)

Com `MODO_DEMONSTRACAO=1` no `.env`, qualquer pessoa que abrir
`https://seu-endereco/demo/` (pelo QR code) entra como socorrista **sem
cadastro nem senha** e faz o fluxo inteiro pelo celular:

- cada visitante ganha uma conta temporária só dele (as emergências de um não
  se misturam com as de outro) — apagada sozinha depois de 24 h;
- o trajeto até o hospital é simulado em cerca de 1 a 2,5 minutos;
- o hospital de destino responde sozinho no chat;
- visitante não envia fotos (o link é público);
- as emergências dos visitantes aparecem normalmente no painel do hospital
  e no dashboard do admin — dá para deixar um deles no telão.

O QR code para projetar fica em `/demo/qrcode` (entre como admin). Ele aponta
para o endereço pelo qual a página foi aberta, então abra-o pelo endereço
público (o `https://` do domínio), não por `127.0.0.1`. Use HTTPS: sem ele o
celular não libera a localização para abrir a ocorrência.

### 6. Manter rodando

No Linux, um serviço do systemd sobe o sistema junto com o computador e o
reinicia se cair (ajuste os caminhos e o usuário):

```ini
# /etc/systemd/system/orbishealth.service
[Unit]
Description=OrbisHealth
After=network-online.target postgresql.service

[Service]
User=seu-usuario
WorkingDirectory=/caminho/para/Orbis Health/backend
ExecStart=/caminho/para/Orbis Health/backend/venv/bin/python run.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now orbishealth
```

No Windows, o Agendador de Tarefas pode rodar
`venv\Scripts\python.exe run.py` (pasta `backend`) ao iniciar o computador.

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
- RN-012: não há autocadastro; o primeiro admin vem do `seed.py` e os demais usuários são cadastrados por um admin.
- RN-014: socorrista com `Usuario.ativo = False` consegue logar normalmente
  (isso será usado para bloquear ações operacionais em etapas futuras).
- RN-015: usuário do papel `hospital` vinculado a um `Hospital.ativo = False`
  tem o login bloqueado.

## Testes

Ver o Plano de Testes (PT-ORBIS-001): suíte funcional em `backend/tests/`
(`pytest --relatorio-pdf=../OrbisHealth_Relatorio_Testes.pdf`) e testes não
funcionais em `backend/testes_nao_funcionais/`.
