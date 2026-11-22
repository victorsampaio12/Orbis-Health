from datetime import datetime, timedelta

import bcrypt
from flask import current_app

from app import db
from app.models.usuario import PapelEnum, Usuario

MENSAGEM_CREDENCIAIS_INVALIDAS = "E-mail ou senha incorretos!"
MENSAGEM_PERFIL_BLOQUEADO = "Perfil temporariamente bloqueado"


class AuthError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def _bloqueio_ativo(usuario):
    return usuario.bloqueado_ate is not None and usuario.bloqueado_ate > datetime.utcnow()


def _limpar_bloqueio_expirado(usuario):
    if usuario.bloqueado_ate is not None and usuario.bloqueado_ate <= datetime.utcnow():
        usuario.bloqueado_ate = None
        usuario.tentativas_falhas = 0
        db.session.commit()


def acesso_revogado(usuario):
    """Conta que não pode mais usar o sistema: admin desativado ou usuário de
    hospital desativado. Vale no login E em toda requisição (ver load_user em
    app/__init__.py) — senão quem já estava logado continuaria entrando.
    Socorrista inativo NÃO entra aqui: pela RN-014 ele loga, só não opera."""
    if usuario.papel == PapelEnum.admin:
        return not usuario.ativo
    if usuario.papel == PapelEnum.hospital:
        return usuario.hospital is not None and not usuario.hospital.ativo
    return False


def autenticar(email, senha):
    """Valida credenciais e regras de bloqueio da HU-001.

    Levanta AuthError com a mensagem exata a ser exibida ao usuário.
    Retorna a instância de Usuario quando o login é permitido.
    """
    usuario = Usuario.query.filter_by(email=email).first()

    if usuario is None:
        raise AuthError(MENSAGEM_CREDENCIAIS_INVALIDAS)

    _limpar_bloqueio_expirado(usuario)

    # Cenário 3: bloqueio por tentativas tem prioridade sobre a senha estar
    # certa ou errada, até o bloqueio expirar.
    if _bloqueio_ativo(usuario):
        raise AuthError(MENSAGEM_PERFIL_BLOQUEADO)

    senha_confere = bcrypt.checkpw(
        senha.encode("utf-8"), usuario.senha_hash.encode("utf-8")
    )

    if not senha_confere:
        usuario.tentativas_falhas += 1

        max_tentativas = current_app.config["MAX_LOGIN_ATTEMPTS"]
        if usuario.tentativas_falhas >= max_tentativas:
            lockout_minutes = current_app.config["LOGIN_LOCKOUT_MINUTES"]
            usuario.bloqueado_ate = datetime.utcnow() + timedelta(minutes=lockout_minutes)

        db.session.commit()
        raise AuthError(MENSAGEM_CREDENCIAIS_INVALIDAS)

    # RN-015 (hospital desativado) e RN-020 (admin desativado): login bloqueado.
    if acesso_revogado(usuario):
        raise AuthError(MENSAGEM_PERFIL_BLOQUEADO)

    # RN-014: socorrista inativo consegue logar normalmente (não verificado aqui).

    usuario.tentativas_falhas = 0
    usuario.bloqueado_ate = None
    db.session.commit()

    return usuario
