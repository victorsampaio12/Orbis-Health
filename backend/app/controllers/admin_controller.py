from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.controllers.decorators import admin_required
from app.services import cadastro_service, dashboard_service, nominatim_client
from app.services.cadastro_service import CadastroError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def index():
    """Painel de Cadastros: hub com as 3 áreas que o admin gerencia. Os
    números pequenos em cada card vêm das mesmas listas das telas de
    listagem — nada de bater no banco duas vezes com lógica diferente."""
    hospitais = cadastro_service.listar_hospitais()
    socorristas = cadastro_service.listar_socorristas()
    admins = cadastro_service.listar_admins()

    resumo = {
        "hospitais": {"total": len(hospitais), "ativos": sum(1 for h in hospitais if h.ativo)},
        "socorristas": {
            "total": len(socorristas),
            "ativos": sum(1 for s in socorristas if s.usuario.ativo),
        },
        "admins": {"total": len(admins), "ativos": sum(1 for a in admins if a.ativo)},
    }
    return render_template("admin/index.html", resumo=resumo)


@admin_bp.route("/dashboard-dados")
@login_required
@admin_required
def dashboard_dados():
    """JSON pro dashboard atualizar os números sozinho, sem recarregar a
    página — só o admin pode bater aqui (RN implícita: KPI do sistema
    inteiro não é algo que hospital/socorrista deveriam ver)."""
    return jsonify(dashboard_service.montar_kpis())


# --------------------------------------------------------------- Hospitais

@admin_bp.route("/geocodificar")
@login_required
@admin_required
def geocodificar():
    """Fallback pro mapa do formulário de hospital: tenta achar de cara o
    texto exato digitado, pro caso do admin não usar o autocomplete (ex:
    colar o endereço e ir direto pro Salvar)."""
    endereco = (request.args.get("endereco") or "").strip()
    if not endereco:
        return jsonify({"latitude": None, "longitude": None})

    coordenadas = nominatim_client.geocodificar_endereco(endereco)
    if not coordenadas:
        return jsonify({"latitude": None, "longitude": None})

    return jsonify({"latitude": coordenadas[0], "longitude": coordenadas[1]})


@admin_bp.route("/enderecos-sugestoes")
@login_required
@admin_required
def enderecos_sugestoes():
    """Autocomplete do campo endereço: lista candidatos reais do Nominatim
    pra escolher, em vez de o admin ter que acertar de primeira o texto
    exato (RN: reduzir erro humano na localização do hospital)."""
    texto = (request.args.get("texto") or "").strip()
    if len(texto) < 4:
        return jsonify({"sugestoes": []})

    return jsonify({"sugestoes": nominatim_client.sugerir_enderecos(texto)})


@admin_bp.route("/hospitais")
@login_required
@admin_required
def listar_hospitais():
    hospitais = cadastro_service.listar_hospitais()
    return render_template("admin/hospitais_lista.html", hospitais=hospitais)


@admin_bp.route("/hospitais/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_hospital():
    if request.method == "POST":
        try:
            hospital = cadastro_service.criar_hospital(request.form, current_user)
        except CadastroError as erro:
            flash(erro.message, "error")
            return render_template("admin/hospital_form.html", dados=request.form)

        flash("Hospital criado com sucesso!", "success")
        if hospital.latitude is None:
            flash(
                "Não conseguimos localizar esse endereço no mapa. O hospital foi "
                "salvo normalmente, mas edite o endereço se quiser corrigir.",
                "warning",
            )
        return redirect(url_for("admin.listar_hospitais"))

    return render_template("admin/hospital_form.html", dados={})


@admin_bp.route("/hospitais/<int:hospital_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_hospital(hospital_id):
    hospital = cadastro_service.obter_hospital(hospital_id)

    if request.method == "POST":
        try:
            hospital_atualizado = cadastro_service.editar_hospital(
                hospital_id, request.form, current_user
            )
        except CadastroError as erro:
            flash(erro.message, "error")
            return render_template(
                "admin/hospital_form.html", dados=request.form, hospital=hospital
            )

        flash("Hospital atualizado com sucesso!", "success")
        if hospital_atualizado.latitude is None:
            flash(
                "Não conseguimos localizar esse endereço no mapa. O hospital foi "
                "salvo normalmente, mas edite o endereço se quiser corrigir.",
                "warning",
            )
        return redirect(url_for("admin.listar_hospitais"))

    dados = {
        "nome": hospital.nome,
        "endereco": hospital.endereco,
        "tem_heliponto": "on" if hospital.tem_heliponto else "",
        "tem_garagem": "on" if hospital.tem_garagem else "",
        "capacidade_maxima": hospital.capacidade_maxima or "",
        "responsavel_nome": hospital.usuario.nome,
        "email": hospital.usuario.email,
    }
    return render_template("admin/hospital_form.html", dados=dados, hospital=hospital)


@admin_bp.route("/hospitais/<int:hospital_id>/status", methods=["POST"])
@login_required
@admin_required
def status_hospital(hospital_id):
    hospital = cadastro_service.alternar_status_hospital(hospital_id, current_user)
    if hospital.ativo:
        flash("Hospital reativado com sucesso!", "success")
    else:
        flash("Hospital desativado com sucesso!", "success")
    return redirect(url_for("admin.listar_hospitais"))


# ------------------------------------------------------------- Socorristas

@admin_bp.route("/socorristas")
@login_required
@admin_required
def listar_socorristas():
    socorristas = cadastro_service.listar_socorristas()
    return render_template("admin/socorristas_lista.html", socorristas=socorristas)


@admin_bp.route("/socorristas/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_socorrista():
    if request.method == "POST":
        try:
            cadastro_service.criar_socorrista(request.form, current_user)
        except CadastroError as erro:
            flash(erro.message, "error")
            return render_template("admin/socorrista_form.html", dados=request.form)

        flash("Socorrista criado com sucesso!", "success")
        return redirect(url_for("admin.listar_socorristas"))

    return render_template("admin/socorrista_form.html", dados={})


@admin_bp.route("/socorristas/<int:socorrista_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_socorrista(socorrista_id):
    socorrista = cadastro_service.obter_socorrista(socorrista_id)

    if request.method == "POST":
        try:
            cadastro_service.editar_socorrista(socorrista_id, request.form, current_user)
        except CadastroError as erro:
            flash(erro.message, "error")
            return render_template(
                "admin/socorrista_form.html", dados=request.form, socorrista=socorrista
            )

        flash("Socorrista atualizado com sucesso!", "success")
        return redirect(url_for("admin.listar_socorristas"))

    dados = {
        "nome": socorrista.usuario.nome,
        "email": socorrista.usuario.email,
        "matricula": socorrista.matricula,
        "telefone": socorrista.telefone or "",
    }
    return render_template(
        "admin/socorrista_form.html", dados=dados, socorrista=socorrista
    )


@admin_bp.route("/socorristas/<int:socorrista_id>/status", methods=["POST"])
@login_required
@admin_required
def status_socorrista(socorrista_id):
    socorrista = cadastro_service.alternar_status_socorrista(socorrista_id, current_user)
    if socorrista.usuario.ativo:
        flash("Socorrista reativado com sucesso!", "success")
    else:
        flash("Socorrista desativado com sucesso!", "success")
    return redirect(url_for("admin.listar_socorristas"))


# ------------------------------------------------------------------ Admins

@admin_bp.route("/admins")
@login_required
@admin_required
def listar_admins():
    admins = cadastro_service.listar_admins()
    return render_template("admin/admins_lista.html", admins=admins)


@admin_bp.route("/admins/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_admin():
    if request.method == "POST":
        try:
            cadastro_service.criar_admin(request.form, current_user)
        except CadastroError as erro:
            flash(erro.message, "error")
            return render_template("admin/admin_form.html", dados=request.form)

        flash("Admin criado com sucesso!", "success")
        return redirect(url_for("admin.listar_admins"))

    return render_template("admin/admin_form.html", dados={})


@admin_bp.route("/admins/<int:admin_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_admin(admin_id):
    admin = cadastro_service.obter_admin(admin_id)

    if request.method == "POST":
        try:
            cadastro_service.editar_admin(admin_id, request.form, current_user)
        except CadastroError as erro:
            flash(erro.message, "error")
            return render_template(
                "admin/admin_form.html", dados=request.form, admin=admin
            )

        flash("Admin atualizado com sucesso!", "success")
        return redirect(url_for("admin.listar_admins"))

    dados = {"nome": admin.nome, "email": admin.email}
    return render_template("admin/admin_form.html", dados=dados, admin=admin)


@admin_bp.route("/admins/<int:admin_id>/status", methods=["POST"])
@login_required
@admin_required
def status_admin(admin_id):
    try:
        admin = cadastro_service.alternar_status_admin(admin_id, current_user)
    except CadastroError as erro:
        flash(erro.message, "error")
        return redirect(url_for("admin.listar_admins"))

    if admin.ativo:
        flash("Admin reativado com sucesso!", "success")
    else:
        flash("Admin desativado com sucesso!", "success")
    return redirect(url_for("admin.listar_admins"))


@admin_bp.route("/admins/<int:admin_id>/excluir", methods=["POST"])
@login_required
@admin_required
def excluir_admin(admin_id):
    try:
        cadastro_service.excluir_admin(admin_id, current_user)
    except CadastroError as erro:
        flash(erro.message, "error")
        return redirect(url_for("admin.listar_admins"))

    flash("Admin excluído com sucesso!", "success")
    return redirect(url_for("admin.listar_admins"))
