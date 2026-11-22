# Prompt para hospedar o OrbisHealth nesta máquina

Cole o texto abaixo no Claude Code desta máquina, aberto na pasta onde o
repositório foi (ou será) clonado.

---

Quero hospedar o OrbisHealth nesta máquina, acessível pela internet com HTTPS,
do mesmo jeito que o sistema da OAB que eu já hospedei aqui. Responda em
português do Brasil.

**O sistema:** OrbisHealth, meu TCC — regulação de emergências estilo SAMU-DF.
Flask + Flask-SocketIO (tempo real), PostgreSQL, Jinja/JS puro. Repositório:
https://github.com/victorsampaio12/Orbis-Health.git (branch `main`). O README
tem a seção "Hospedar em outro computador", com o passo a passo e as variáveis
do `.env`; leia antes de começar.

**Como hospedar:** primeiro descubra como o sistema da OAB está publicado
nesta máquina — procure serviços do systemd, configuração de nginx/Caddy/
Apache, Cloudflare Tunnel (`cloudflared`), Docker/docker-compose, certificados,
domínio/subdomínio e portas em uso. Me mostre o que encontrou e proponha
publicar o OrbisHealth no mesmo esquema (ex.: um subdomínio novo apontando
para ele), **sem mexer no sistema da OAB**. Espere eu aprovar antes de mudar
DNS, firewall, roteador ou a configuração do proxy.

**Passos esperados:**
1. Clonar (ou `git pull`) o repositório; criar o virtualenv em `backend/venv`
   e instalar `backend/requirements.txt` dentro dele (nunca no Python do
   sistema).
2. PostgreSQL: criar um banco `orbis_health` e um usuário próprio com senha
   forte (se já houver Postgres por causa da OAB, reaproveite o servidor, mas
   com banco e usuário separados).
3. Criar `backend/.env` a partir de `backend/.env.example`:
   - `SECRET_KEY` nova e forte: `python -c "import secrets; print(secrets.token_hex(32))"`
   - dados do banco;
   - `HOST=127.0.0.1` e uma `PORT` livre (5000 se estiver livre) — o acesso
     externo passa só pelo proxy/túnel, nunca direto na porta do Flask;
   - `ATRAS_DE_PROXY=1` (obrigatório atrás de proxy HTTPS: sem isso o login
     pelo `https://` dá erro 403);
   - `MODO_DEMONSTRACAO=1` (libera a entrada pelo QR code em `/demo/`);
   - `FLASK_DEBUG=0`.
   O `.env` nunca vai para o Git.
4. Dentro de `backend/` com o venv ativo: `flask db upgrade`, `python seed.py`
   (admin) e `python seed_demo.py` (44 hospitais públicos do DF e Entorno,
   socorristas e ocorrências de demonstração).
5. Serviço do systemd para `backend/venv/bin/python run.py` (com
   `WorkingDirectory=.../backend`, `Restart=on-failure`, iniciando com a
   máquina e depois do PostgreSQL) — no mesmo estilo do serviço da OAB, se ele
   usar systemd.
6. Proxy/túnel com HTTPS para `127.0.0.1:PORT`. O sistema usa WebSocket
   (Socket.IO em `/socket.io/`): no nginx, repasse os cabeçalhos `Upgrade` e
   `Connection` e `X-Forwarded-Proto`; Caddy e Cloudflare Tunnel já fazem isso.
7. Testar pelo endereço público `https://`:
   - `/login` abre e o login funciona (admin: `admin@orbishealth.com` /
     `Admin@123`) — depois **me peça uma senha nova e troque** (tela Perfil),
     porque essa senha está publicada no README;
   - `/demo/` abre e "Começar como socorrista" leva ao formulário de nova
     ocorrência;
   - `/demo/qrcode` (logado como admin) mostra o QR code com o endereço
     público `https://` — é ele que vou projetar na apresentação;
   - o tempo real funciona (o painel atualiza sem recarregar).
8. Reiniciar a máquina (ou o serviço) e confirmar que volta sozinho.

No final, me passe: o endereço público, como ver os logs, como reiniciar o
serviço e como atualizar o sistema depois (`git pull` + `pip install -r` +
`flask db upgrade` + reiniciar o serviço).
