from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user

from app.models.usuario import PapelEnum

MENSAGEM_ACESSO_NEGADO = "Acesso negado: esta área é restrita a administradores."
MENSAGEM_ACESSO_NEGADO_SOCORRISTA = "Acesso negado: esta área é restrita a socorristas."


def admin_required(view_func):
    """Libera a rota apenas para usuários logados com papel = admin.

    Cobre os dois casos pedidos: usuário não logado (manda para o login) e
    usuário logado com outro papel (manda de volta pro dashboard dele com
    mensagem de acesso negado).
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        if current_user.papel != PapelEnum.admin:
            flash(MENSAGEM_ACESSO_NEGADO, "error")
            return redirect(url_for("auth.dashboard"))

        return view_func(*args, **kwargs)

    return wrapper


def socorrista_required(view_func):
    """Libera a rota apenas para usuários logados com papel = socorrista.

    RN-014 (status ativo/inativo) não é checado aqui — isso é regra de
    login e de operação específica (ex: criar ocorrência), não de acesso
    à rota em si.
    """

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        if current_user.papel != PapelEnum.socorrista:
            flash(MENSAGEM_ACESSO_NEGADO_SOCORRISTA, "error")
            return redirect(url_for("auth.dashboard"))

        return view_func(*args, **kwargs)

    return wrapper
