"""
Fixtures e hooks da suíte de testes end-to-end (pytest + Playwright).

Infraestrutura (tudo descartável e isolado do ambiente real — nunca toca o
`.env`, o Postgres da porta 5432 nem o servidor da porta 5000):

- `servidor` (sessão, autouse): sobe um Postgres via Docker, roda as
  migrations, semeia o admin inicial e inicia o servidor Flask/SocketIO
  real num processo separado (porta 5599). No fim, derruba tudo.
- `db_app`: app Flask só com contexto de aplicação, para asserts diretos
  no banco via SQLAlchemy.
- `anon_page` / `admin_page` / `soc_page` / `hosp_page`: uma aba de
  navegador por perfil, com escopo de CLASSE — os testes de uma classe
  compartilham a mesma sessão e rodam em sequência, como uma jornada real
  de uso.

Com `pytest --relatorio-pdf=arquivo.pdf`, gera também um relatório em PDF
com o resultado de cada teste, os prints de tela, a cobertura de rotas e
de regras de negócio (ver relatorio_pdf.py).
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import pytest

from relatorio_pdf import ColetorRelatorio

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PORT = 55990
DB_NAME = "orbis_health_pytest"
APP_PORT = 5599
BASE_URL = f"http://localhost:{APP_PORT}"
CONTAINER_NAME = "orbis_pytest_pg"
UPLOADS_TESTE = tempfile.mkdtemp(prefix="orbis_uploads_")

TEST_ENV = {
    "SECRET_KEY": "pytest-secret",
    "DB_HOST": "localhost",
    "DB_PORT": str(DB_PORT),
    "DB_NAME": DB_NAME,
    "DB_USER": "postgres",
    "DB_PASSWORD": "pytest",
    "MAX_LOGIN_ATTEMPTS": "5",
    "LOGIN_LOCKOUT_MINUTES": "15",
    "UPLOAD_FOLDER": UPLOADS_TESTE,  # fotos dos testes não vão pra backend/uploads
    "MODO_DEMONSTRACAO": "1",  # libera /demo (test_6_modo_demonstracao.py)
    # sem proxy HTTPS na frente: não herdar o ATRAS_DE_PROXY do .env real
    "ATRAS_DE_PROXY": "0",
}

VIEWPORT = {"width": 1600, "height": 1800}


# ------------------------------------------------------------------ hooks

def pytest_addoption(parser):
    parser.addoption(
        "--relatorio-pdf",
        action="store",
        default=None,
        metavar="ARQUIVO",
        help="Gera um relatório PDF com resultados, prints e cobertura.",
    )


def pytest_configure(config):
    destino = config.getoption("--relatorio-pdf")
    if destino:
        config._coletor_relatorio = ColetorRelatorio(os.path.abspath(destino))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    coletor = getattr(item.config, "_coletor_relatorio", None)
    if coletor:
        coletor.registrar(item, resultado.get_result())


def pytest_sessionfinish(session, exitstatus):
    coletor = getattr(session.config, "_coletor_relatorio", None)
    if coletor:
        caminho = coletor.gerar_pdf(
            log_servidor=getattr(session.config, "_log_servidor", None),
            backend_dir=BACKEND_DIR,
            test_env=TEST_ENV,
        )
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_line(f"Relatório PDF gerado em: {caminho}", green=True)


# --------------------------------------------------------------- fixtures

def _esperar_porta(host, port, timeout):
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _semear_admin_inicial():
    """Único dado que não dá pra criar pela interface: o primeiro admin."""
    sys.path.insert(0, BACKEND_DIR)
    import bcrypt
    from app import create_app, db
    from app.models.usuario import PapelEnum, Usuario
    from app.services import cadastro_service

    app = create_app()
    with app.app_context():
        admin0 = Usuario(
            nome="Admin Zero",
            email="admin0@t.com",
            senha_hash=bcrypt.hashpw(b"Senha@123", bcrypt.gensalt()).decode(),
            papel=PapelEnum.admin,
            ativo=True,
        )
        db.session.add(admin0)
        db.session.commit()

        # hospital de apoio: usado pelos testes de desativação e de RN-015
        cadastro_service.criar_hospital(
            {
                "nome": "Hospital Santa Luzia",
                "endereco": "Hospital Santa Luzia, SHLS, SQS 316, Brasília, Distrito Federal",
                "latitude": "-15.82697",
                "longitude": "-47.9305073",
                "capacidade_maxima": "8",
                "tem_garagem": "on",
                "tem_heliponto": "",
                "responsavel_nome": "Resp Santa Luzia",
                "email": "hospapoio@t.com",
                "senha": "Senha@123",
            },
            admin0,
        )


@pytest.fixture(scope="session", autouse=True)
def servidor(request):
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
    subprocess.run(
        [
            "docker", "run", "-d", "--name", CONTAINER_NAME,
            "-e", "POSTGRES_PASSWORD=pytest",
            "-e", f"POSTGRES_DB={DB_NAME}",
            "-p", f"{DB_PORT}:5432",
            "postgres:15",
        ],
        check=True, capture_output=True, text=True,
    )
    log_path = os.path.join(tempfile.mkdtemp(prefix="orbis_pytest_"), "servidor.log")
    request.config._log_servidor = log_path
    try:
        assert _esperar_porta("localhost", DB_PORT, timeout=30), "Postgres de teste não subiu."
        time.sleep(2)  # a porta abre um pouco antes do Postgres aceitar conexões

        env = {**os.environ, **TEST_ENV, "FLASK_APP": "run.py"}
        subprocess.run(
            [sys.executable, "-m", "flask", "db", "upgrade"],
            cwd=BACKEND_DIR, env=env, check=True, capture_output=True, text=True,
        )

        os.environ.update(TEST_ENV)
        _semear_admin_inicial()

        with open(log_path, "w") as log:
            processo = subprocess.Popen(
                [
                    sys.executable, "-c",
                    f"from run import app, socketio; "
                    f"socketio.run(app, port={APP_PORT}, allow_unsafe_werkzeug=True)",
                ],
                cwd=BACKEND_DIR, env=env, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                assert _esperar_porta("localhost", APP_PORT, timeout=20), "Servidor de teste não subiu."
                yield BASE_URL
            finally:
                processo.terminate()
                try:
                    processo.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    processo.kill()
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
        shutil.rmtree(UPLOADS_TESTE, ignore_errors=True)


@pytest.fixture(scope="session")
def db_app(servidor):
    """Depende de `servidor` pra garantir que as variáveis de ambiente de
    teste já foram aplicadas antes de criar o app (senão poderia cair no
    .env real)."""
    os.environ.update(TEST_ENV)
    sys.path.insert(0, BACKEND_DIR)
    from app import create_app, db

    app = create_app()
    with app.app_context():
        yield app
        db.session.remove()


# Os avisos somem da tela depois de 4 s, e em páginas pesadas (mapa) o
# carregamento pode passar disso. Por isso o teste os registra no instante em
# que aparecem, em vez de procurar na tela depois:
# - window.__flashes: avisos que o servidor mandou exibir nesta página;
# - sessionStorage "__avisos": todo aviso que surgiu nesta aba, inclusive os
#   que chegam em tempo real pelo WebSocket — sobrevive a recargas da página.
CAPTURAR_FLASH = """
(() => {
    const registrar = (texto) => {
        try {
            const lista = JSON.parse(sessionStorage.getItem("__avisos") || "[]");
            lista.push(texto);
            sessionStorage.setItem("__avisos", JSON.stringify(lista));
        } catch (e) { /* página sem sessionStorage (ex.: about:blank) */ }
    };
    document.addEventListener("DOMContentLoaded", () => {
        window.__flashes = Array.from(
            document.querySelectorAll("#flash-container .flash"), (el) => el.innerText.trim()
        );
        window.__flashes.forEach(registrar);
        const container = document.getElementById("flash-container");
        if (!container) return;
        new MutationObserver((mudancas) => mudancas.forEach((m) => m.addedNodes.forEach((no) => {
            if (no.classList && no.classList.contains("flash")) registrar(no.textContent.trim());
        }))).observe(container, { childList: true });
    });
})();
"""


def _nova_pagina(browser, **opcoes):
    # fuso fixo: o resultado não pode depender do relógio da máquina que roda
    context = browser.new_context(viewport=VIEWPORT, timezone_id="America/Sao_Paulo", **opcoes)
    context.add_init_script(CAPTURAR_FLASH)
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    return context, page


@pytest.fixture(scope="class")
def anon_page(browser):
    context, page = _nova_pagina(browser)
    yield page
    context.close()


@pytest.fixture(scope="class")
def admin_page(browser):
    context, page = _nova_pagina(browser)
    yield page
    context.close()


@pytest.fixture(scope="class")
def soc_page(browser):
    context, page = _nova_pagina(
        browser,
        # ~400 m do Hospital de Base: fora do raio de chegada (200 m), então a
        # chegada só é liberada depois que o trajeto simulado de fato roda.
        geolocation={"latitude": -15.8040, "longitude": -47.8884},
        permissions=["geolocation"],
    )
    yield page
    context.close()


@pytest.fixture(scope="class")
def hosp_page(browser):
    context, page = _nova_pagina(browser)
    yield page
    context.close()
