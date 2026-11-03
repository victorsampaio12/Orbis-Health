import os

from flask import Flask, flash, redirect, request, send_from_directory, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

from app.config.config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
# async_mode="threading": não exige eventlet/gevent, roda com o próprio
# servidor de desenvolvimento do Werkzeug — suficiente pro ambiente local.
# Numa instância de produção real, trocar por eventlet/gevent + um servidor
# WSGI assíncrono de verdade.
socketio = SocketIO(async_mode="threading")


def create_app():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(backend_dir)
    template_folder = os.path.join(project_root, "frontend", "templates")
    static_folder = os.path.join(project_root, "frontend", "static")

    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    socketio.init_app(app)

    from app.models.usuario import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    from app.controllers.auth_controller import auth_bp
    app.register_blueprint(auth_bp)

    from app.controllers.admin_controller import admin_bp
    app.register_blueprint(admin_bp)

    from app.controllers.pages_controller import pages_bp
    app.register_blueprint(pages_bp)

    from app.controllers.ocorrencia_controller import ocorrencia_bp
    app.register_blueprint(ocorrencia_bp)

    from app.controllers.inbox_controller import inbox_bp
    app.register_blueprint(inbox_bp)

    from app import socketio_events  # noqa: F401 registra os handlers via decorator

    @app.route("/sw.js")
    def service_worker():
        # Precisa ser servido na raiz (não em /static/sw.js): o escopo padrão
        # de um service worker é o diretório de onde ele é carregado, então
        # servindo em /static/ ele nunca controlaria o resto do app.
        return send_from_directory(static_folder, "sw.js", mimetype="application/javascript")

    @app.errorhandler(413)
    def envio_grande_demais(_erro):
        # Fotos somando mais que MAX_CONTENT_LENGTH num único envio.
        flash("Os arquivos enviados são grandes demais. Envie no máximo 60 MB por vez "
              "(até 10 MB por foto).", "error")
        return redirect(request.referrer or url_for("auth.dashboard"))

    app.jinja_env.filters["iniciais"] = _iniciais
    app.jinja_env.filters["codigo_emg"] = lambda ocorrencia_id: f"EMG-{ocorrencia_id:04d}"
    app.jinja_env.globals["url_filtro"] = _url_filtro

    from app.models.usuario import PapelEnum
    from app.services import ocorrencia_service

    @app.context_processor
    def inject_preferencias():
        from app.services import conta_service

        if current_user.is_authenticated:
            return {"preferencias": conta_service.obter_preferencias(current_user)}
        return {"preferencias": conta_service.PREFERENCIAS_PADRAO}

    @app.context_processor
    def inject_ocorrencia_ativa_sidebar():
        if current_user.is_authenticated and current_user.papel == PapelEnum.socorrista:
            ativa = ocorrencia_service.obter_ocorrencia_ativa_do_socorrista(current_user)
            return {"ocorrencia_ativa_sidebar": ativa}
        return {"ocorrencia_ativa_sidebar": None}

    @app.context_processor
    def inject_inbox_nao_lidas():
        from app.services import chat_service

        if current_user.is_authenticated and current_user.papel in (
            PapelEnum.socorrista,
            PapelEnum.hospital,
        ):
            return {"inbox_nao_lidas": chat_service.contar_nao_lidas(current_user)}
        return {"inbox_nao_lidas": 0}

    return app


def _iniciais(nome):
    partes = (nome or "").split()
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][0].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def _url_filtro(endpoint=None, **sobrescreve):
    """Monta uma URL reaproveitando os parâmetros da página atual (querystring),
    trocando só o que for passado — usado na paginação, no seletor de 'por
    página' e no botão de exportar do Histórico, pra nunca perder os filtros
    já aplicados. `endpoint` é só pra apontar pra uma rota diferente (ex: a
    de exportar); sem ele, aponta pra própria página atual."""
    args = request.args.to_dict()
    args.update(sobrescreve)
    args = {chave: valor for chave, valor in args.items() if valor not in (None, "")}
    return url_for(endpoint or request.endpoint, **args)
