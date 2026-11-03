from datetime import datetime

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services import conta_service, historico_service
from app.services.conta_service import ContaError

pages_bp = Blueprint("pages", __name__)


# ------------------------------------------------------------------ Perfil

@pages_bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        try:
            conta_service.atualizar_perfil(current_user, request.form)
        except ContaError as erro:
            flash(erro.message, "error")
            return render_template("perfil.html", dados=request.form)

        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("pages.perfil"))

    return render_template("perfil.html", dados={})


@pages_bp.route("/perfil/senha", methods=["POST"])
@login_required
def alterar_senha():
    try:
        conta_service.alterar_senha(
            current_user,
            request.form.get("senha_atual"),
            request.form.get("nova_senha"),
            request.form.get("confirmacao"),
        )
    except ContaError as erro:
        flash(erro.message, "error")
    else:
        flash("Senha alterada com sucesso!", "success")
    return redirect(url_for("pages.perfil"))


# ------------------------------------------------------------ Preferências

@pages_bp.route("/preferencias", methods=["GET", "POST"])
@login_required
def preferencias():
    if request.method == "POST":
        try:
            conta_service.salvar_preferencias(current_user, request.form)
        except ContaError as erro:
            flash(erro.message, "error")
        else:
            flash("Preferências salvas com sucesso!", "success")
        return redirect(url_for("pages.preferencias"))

    return render_template("preferencias.html")


@pages_bp.route("/preferencias/menu", methods=["POST"])
@login_required
def preferencia_menu():
    recolhido = (request.get_json(silent=True) or {}).get("recolhido")
    if not isinstance(recolhido, bool):
        return jsonify({"ok": False}), 400
    conta_service.salvar_menu_recolhido(current_user, recolhido)
    return jsonify({"ok": True})


def _data(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date() if valor else None
    except ValueError:
        return None


def _filtros_historico():
    return {
        "busca": request.args.get("busca", ""),
        "status": request.args.get("status") or None,
        "veiculo": request.args.get("veiculo") or None,
        "data_inicio": _data(request.args.get("data_inicio")),
        "data_fim": _data(request.args.get("data_fim")),
    }


@pages_bp.route("/emergencias/historico")
@login_required
def historico_emergencias():
    if current_user.papel.value != "hospital" or current_user.hospital is None:
        abort(403)

    filtros = _filtros_historico()
    try:
        pagina = int(request.args.get("pagina", 1))
    except ValueError:
        pagina = 1
    try:
        por_pagina = int(request.args.get("por_pagina", historico_service.POR_PAGINA_PADRAO))
    except ValueError:
        por_pagina = historico_service.POR_PAGINA_PADRAO
    por_pagina = por_pagina if por_pagina in (8, 16, 24) else historico_service.POR_PAGINA_PADRAO

    resultado = historico_service.listar(current_user.hospital, filtros, pagina, por_pagina)
    paginas_visiveis = historico_service.paginas_visiveis(
        resultado["pagina"], resultado["total_paginas"]
    )

    return render_template(
        "historico_emergencias.html",
        filtros=filtros,
        resultado=resultado,
        paginas_visiveis=paginas_visiveis,
    )


@pages_bp.route("/emergencias/historico/exportar")
@login_required
def historico_emergencias_exportar():
    if current_user.papel.value != "hospital" or current_user.hospital is None:
        abort(403)

    csv_texto = historico_service.exportar_csv(current_user.hospital, _filtros_historico())
    nome_arquivo = f"historico-emergencias-{datetime.utcnow():%Y%m%d-%H%M}.csv"
    return Response(
        "﻿" + csv_texto,  # BOM: Excel abre acentuação certa sem isso
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )
