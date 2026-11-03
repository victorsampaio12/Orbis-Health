"""Inbox = histórico de conversas das emergências FINALIZADAS (somente
leitura). A conversa de uma emergência em andamento acontece na própria
tela da ocorrência."""

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.services import chat_service, ocorrencia_service
from app.services.ocorrencia_service import AcessoNaoAutorizadoError

inbox_bp = Blueprint("inbox", __name__, url_prefix="/inbox")


@inbox_bp.route("/")
@login_required
def index():
    conversas = chat_service.listar_conversas(current_user)
    return render_template("inbox.html", conversas=conversas, ocorrencia_ativa=None)


@inbox_bp.route("/<int:ocorrencia_id>")
@login_required
def conversa(ocorrencia_id):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)

    try:
        ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, current_user)
    except AcessoNaoAutorizadoError as erro:
        flash(erro.message, "error")
        return redirect(url_for("inbox.index"))

    if ocorrencia.status.value != "finalizada":
        # Emergência ainda em andamento: o chat vive na tela da ocorrência.
        return redirect(url_for("ocorrencia.ver", ocorrencia_id=ocorrencia_id))

    # Marca como lidas ANTES de montar a lista abaixo, pra o badge já sumir
    # na mesma carga de página (sem isso, o contador ficava um passo atrasado).
    chat_service.marcar_como_lidas(ocorrencia_id, current_user)

    eh_socorrista = current_user.papel.value == "socorrista"
    outro_nome = ocorrencia.hospital.nome if eh_socorrista else ocorrencia.socorrista.usuario.nome
    outro_papel = "Hospital" if eh_socorrista else "Socorrista"
    outro_telefone = None if eh_socorrista else ocorrencia.socorrista.telefone

    return render_template(
        "inbox.html",
        conversas=chat_service.listar_conversas(current_user),
        ocorrencia_ativa=ocorrencia,
        outro_nome=outro_nome,
        outro_papel=outro_papel,
        outro_telefone=outro_telefone,
    )
