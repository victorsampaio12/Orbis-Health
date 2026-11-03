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

    # RN-015: usuário vinculado a hospital desativado tem o login bloqueado.
    if usuario.papel == PapelEnum.hospital and usuario.hospital is not None:
        if not usuario.hospital.ativo:
            raise AuthError(MENSAGEM_PERFIL_BLOQUEADO)

    # RN-014: socorrista inativo consegue logar normalmente (não verificado aqui).

    usuario.tentativas_falhas = 0
    usuario.bloqueado_ate = None
    db.session.commit()

    return usuario
