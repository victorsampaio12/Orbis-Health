"""Modo demonstração (TCC): entrada sem cadastro pelo QR code e a página
com o QR code para projetar. Tudo responde 404 se MODO_DEMONSTRACAO=0."""

import segno
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.services import demo_service
from app.services.demo_service import DemoError

demo_bp = Blueprint("demo", __name__, url_prefix="/demo")


@demo_bp.before_request
def exigir_modo_demonstracao():
    if not demo_service.ativo():
        abort(404)


@demo_bp.route("/")
def entrada():
    if current_user.is_authenticated and demo_service.eh_visitante(current_user):
        return redirect(url_for("auth.dashboard"))
    return render_template("demo/entrada.html")


@demo_bp.route("/entrar", methods=["POST"])
def entrar():
    if current_user.is_authenticated and demo_service.eh_visitante(current_user):
        return redirect(url_for("auth.dashboard"))
    try:
        visitante = demo_service.criar_visitante(request.remote_addr)
    except DemoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("demo.entrada"))
    if current_user.is_authenticated:
        logout_user()
    # "lembrar" mantém o visitante na mesma conta se ele fechar o navegador
    login_user(visitante, remember=True)
    return redirect(url_for("auth.dashboard"))


@demo_bp.route("/qrcode")
@login_required
def qrcode():
    """Para projetar na apresentação: o QR code aponta para /demo deste servidor."""
    if current_user.papel.value not in ("admin", "hospital"):
        abort(403)
    endereco = url_for("demo.entrada", _external=True)
    svg = segno.make(endereco, error="m").svg_inline(border=2, dark="#0f172a", omitsize=True)
    return render_template("demo/qrcode.html", endereco=endereco, svg=svg)
