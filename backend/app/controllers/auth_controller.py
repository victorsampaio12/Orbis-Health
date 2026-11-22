import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.services import dashboard_service, ocorrencia_service, painel_service, rota_service
from app.services.auth_service import AuthError, autenticar

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    return redirect(url_for("auth.login"))


def _tela_login():
    from app.models.hospital import Hospital

    return render_template("login.html", total_hospitais=Hospital.query.filter_by(ativo=True).count())


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        try:
            usuario = autenticar(email, senha)
        except AuthError as erro:
            flash(erro.message, "error")
            return _tela_login()

        login_user(usuario)
        flash("Login com Sucesso!", "success")
        return redirect(url_for("auth.dashboard"))

    return _tela_login()


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.papel.value == "hospital" and current_user.hospital is not None:
        hospital = current_user.hospital
        painel = {
            "hospital": {
                "id": hospital.id,
                "nome": hospital.nome,
                "posicao": (
                    [hospital.latitude, hospital.longitude]
                    if hospital.latitude is not None
                    else None
                ),
            },
            "emergencias": painel_service.montar_emergencias(hospital),
            "raio_chegada_km": rota_service.RAIO_CHEGADA_KM,
        }
        return render_template(
            "ocorrencias/dashboard_hospital.html",
            hospital=hospital,
            emergencias=painel["emergencias"],
            # "<" escapado: o JSON vai dentro de um <script> e tem texto livre
            # (local, nomes) — sem isso um "</script>" digitado quebraria a página.
            painel_json=json.dumps(painel).replace("<", "\\u003c"),
        )

    if current_user.papel.value == "socorrista":
        ativa = ocorrencia_service.obter_ocorrencia_ativa_do_socorrista(current_user)
        if ativa is not None:
            return redirect(url_for("ocorrencia.ver", ocorrencia_id=ativa.id))
        return redirect(url_for("ocorrencia.nova"))

    # Só sobra o admin — os outros dois papéis retornam antes.
    return render_template("admin/dashboard.html", kpis=dashboard_service.montar_kpis())


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Usuário deslogado com sucesso!", "success")
    return redirect(url_for("auth.login"))
