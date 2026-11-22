"""
Ambiente descartável para os testes não funcionais (seção 7.2 do Plano de
Testes): sobe um PostgreSQL em Docker, aplica as migrations, cria o admin e
popula com os dados de demonstração de Brasília (seed_demo.py), e inicia o
servidor real num processo separado.

Nunca usa o `.env`, o Postgres da porta 5432 nem o servidor da porta 5000.

Uso típico:

    with Ambiente(porta_db=55991, porta_app=5598) as amb:
        s = amb.sessao("hbdf@orbishealth.com")
        s.get(amb.url + "/dashboard")
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import requests

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTADOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
SENHA = "Senha@123"
ADMIN_EMAIL = "admin@orbishealth.com"
ADMIN_SENHA = "Admin@123"


def esperar_porta(host, porta, timeout):
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            with socket.create_connection((host, porta), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def salvar_resultado(nome, dados):
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    caminho = os.path.join(RESULTADOS_DIR, f"{nome}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=str)
    print(f"-> resultado salvo em {caminho}")
    return caminho


class Ambiente:
    def __init__(self, porta_db=55991, porta_app=5598, semear=True, extra_env=None, nome="orbis_nf_pg"):
        self.porta_db = porta_db
        self.porta_app = porta_app
        self.container = f"{nome}_{porta_db}"
        self.url = f"http://localhost:{porta_app}"
        self.semear = semear
        self.uploads = tempfile.mkdtemp(prefix="orbis_nf_uploads_")
        self.log_path = os.path.join(tempfile.mkdtemp(prefix="orbis_nf_log_"), "servidor.log")
        self.env = {
            **os.environ,
            "SECRET_KEY": "nf-secret",
            "DB_HOST": "localhost",
            "DB_PORT": str(porta_db),
            "DB_NAME": "orbis_nf",
            "DB_USER": "postgres",
            "DB_PASSWORD": "nf",
            "UPLOAD_FOLDER": self.uploads,
            "FLASK_APP": "run.py",
            # o .env real pode ter ATRAS_DE_PROXY=1 (cookie só via HTTPS);
            # aqui não há proxy na frente
            "ATRAS_DE_PROXY": "0",
            **(extra_env or {}),
        }
        self.processo = None

    # ------------------------------------------------------------ banco
    def subir_banco(self):
        subprocess.run(["docker", "rm", "-f", self.container], capture_output=True)
        subprocess.run(
            ["docker", "run", "-d", "--name", self.container,
             "-e", "POSTGRES_PASSWORD=nf", "-e", "POSTGRES_DB=orbis_nf",
             "-p", f"{self.porta_db}:5432", "postgres:15"],
            check=True, capture_output=True, text=True,
        )
        assert esperar_porta("localhost", self.porta_db, 30), "Postgres não subiu"
        self.esperar_banco_pronto()

    def esperar_banco_pronto(self, timeout=30):
        inicio = time.time()
        while time.time() - inicio < timeout:
            r = subprocess.run(["docker", "exec", self.container, "pg_isready", "-U", "postgres"],
                               capture_output=True)
            if r.returncode == 0:
                time.sleep(1)
                return
            time.sleep(0.5)
        raise RuntimeError("Postgres não ficou pronto")

    def psql(self, sql):
        r = subprocess.run(
            ["docker", "exec", "-i", self.container, "psql", "-U", "postgres", "-d", "orbis_nf",
             "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
            capture_output=True, text=True,
        )
        return r.returncode, (r.stdout + r.stderr).strip()

    def flask(self, *args, check=True):
        return subprocess.run([sys.executable, "-m", "flask", *args], cwd=BACKEND_DIR, env=self.env,
                              capture_output=True, text=True, check=check)

    def python(self, codigo, check=True):
        return subprocess.run([sys.executable, "-c", codigo], cwd=BACKEND_DIR, env=self.env,
                              capture_output=True, text=True, check=check)

    def popular(self):
        self.flask("db", "upgrade")
        self.python(
            "import bcrypt\n"
            "from app import create_app, db\n"
            "from app.models.usuario import PapelEnum, Usuario\n"
            "app = create_app()\n"
            "with app.app_context():\n"
            f"    db.session.add(Usuario(nome='Administrador', email='{ADMIN_EMAIL}', "
            f"senha_hash=bcrypt.hashpw(b'{ADMIN_SENHA}', bcrypt.gensalt()).decode(), "
            "papel=PapelEnum.admin, ativo=True))\n"
            "    db.session.commit()\n"
        )
        r = subprocess.run([sys.executable, "seed_demo.py"], cwd=BACKEND_DIR, env=self.env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)

    # --------------------------------------------------------- servidor
    def subir_servidor(self):
        log = open(self.log_path, "a")
        self.processo = subprocess.Popen(
            [sys.executable, "-c",
             "from run import app, socketio; "
             f"socketio.run(app, port={self.porta_app}, allow_unsafe_werkzeug=True)"],
            cwd=BACKEND_DIR, env=self.env, stdout=log, stderr=subprocess.STDOUT,
        )
        assert esperar_porta("localhost", self.porta_app, 30), "Servidor não subiu"
        return self.processo

    def derrubar_servidor(self, sinal="terminate"):
        if self.processo and self.processo.poll() is None:
            getattr(self.processo, sinal)()
            try:
                self.processo.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.processo.kill()
        self.processo = None

    # ----------------------------------------------------------- sessão
    def sessao(self, email, senha=SENHA):
        s = requests.Session()
        r = s.post(f"{self.url}/login", data={"email": email, "senha": senha}, allow_redirects=False)
        assert r.status_code in (302, 303), f"login falhou para {email}: {r.status_code}"
        return s

    # -------------------------------------------------------- contexto
    def __enter__(self):
        self.subir_banco()
        if self.semear:
            self.popular()
        else:
            self.flask("db", "upgrade")
        self.subir_servidor()
        return self

    def __exit__(self, *exc):
        self.derrubar_servidor()
        subprocess.run(["docker", "rm", "-f", self.container], capture_output=True)
        shutil.rmtree(self.uploads, ignore_errors=True)
        return False
