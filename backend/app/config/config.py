import os
import secrets


class Config:
    # Sem SECRET_KEY no ambiente, gera uma aleatória a cada início: as sessões
    # caem quando o servidor reinicia, mas ninguém consegue forjar um cookie de
    # sessão com uma chave conhecida (a antiga "dev-secret-key" estava no Git).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # Cookie de sessão: inacessível ao JavaScript e não enviado em POSTs
    # vindos de outros sites (primeira barreira contra CSRF; a segunda é a
    # checagem de origem em app/__init__.py).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # ATRAS_DE_PROXY=1 no .env quando houver um proxy reverso com HTTPS na
    # frente do servidor (ver app/__init__.py e a seção de hospedagem do README).
    ATRAS_DE_PROXY = os.environ.get("ATRAS_DE_PROXY", "0").lower() in ("1", "true", "sim")

    # MODO_DEMONSTRACAO=1: libera /demo (entrada sem cadastro pelo QR code,
    # para a apresentação do TCC). Ver app/services/demo_service.py.
    MODO_DEMONSTRACAO = os.environ.get("MODO_DEMONSTRACAO", "0").lower() in ("1", "true", "sim")

    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "orbis_health")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Testa a conexão antes de usá-la: se o PostgreSQL reiniciou, a conexão
    # morta do pool é descartada em vez de virar erro 500 para o usuário.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # HU-001, cenário 3: após MAX_LOGIN_ATTEMPTS tentativas incorretas seguidas,
    # o usuário fica bloqueado por LOGIN_LOCKOUT_MINUTES minutos.
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", 5))

    # Fotos anexadas ao prontuário: ficam em disco, fora da pasta static (só
    # são servidas por rota protegida). Limite total por envio de formulário.
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads"),
    )
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024

    # O banco guarda horários em UTC; este é o fuso da operação, usado pelo
    # servidor pra decidir "que dia é hoje", filtrar por data e exportar CSV.
    FUSO_HORARIO = os.environ.get("FUSO_HORARIO", "America/Sao_Paulo")
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", 15))

    # Geocodificação (Nominatim) e roteamento terrestre (OSRM). Por padrão
    # apontam pros servidores públicos de demonstração — sem SLA, sem chave
    # de API, com política de uso justo. Trocar por uma instância própria
    # no futuro é só mudar estas duas variáveis.
    NOMINATIM_BASE_URL = os.environ.get(
        "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"
    )
    OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
    MAPS_USER_AGENT = os.environ.get("MAPS_USER_AGENT", "OrbisHealth-UCB/1.0")
