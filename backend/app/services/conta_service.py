"""Perfil e preferências da própria conta (qualquer papel).

Diferente do cadastro_service, que é o ADMIN gerenciando contas dos outros:
aqui o usuário só mexe nos dados dele, e o e-mail de login fica de fora de
propósito (identidade de login é do admin, RN-012).
"""

import bcrypt

from app import db
from app.models.usuario import PapelEnum
from app.services.cadastro_service import SENHA_MIN_LENGTH

TELEFONE_MAX = 30

PREFERENCIAS_PADRAO = {
    "menu_recolhido": False,
    "som_chat": True,
    "som_nova_emergencia": True,
    "formato_hora": "24h",
}
FORMATOS_HORA = ("24h", "12h")


class ContaError(Exception):
    def __init__(self, message, campo=None):
        self.message = message
        self.campo = campo
        super().__init__(message)


# ------------------------------------------------------------------ Perfil

def atualizar_perfil(usuario, dados):
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise ContaError("O campo nome é obrigatório.", campo="nome")

    usuario.nome = nome

    # Telefone só existe pro socorrista (aparece pro hospital nos cards).
    if usuario.papel == PapelEnum.socorrista and usuario.socorrista is not None:
        telefone = (dados.get("telefone") or "").strip()
        if len(telefone) > TELEFONE_MAX:
            raise ContaError(
                f"O telefone deve ter no máximo {TELEFONE_MAX} caracteres.",
                campo="telefone",
            )
        usuario.socorrista.telefone = telefone or None

    db.session.commit()
    return usuario


def alterar_senha(usuario, senha_atual, nova_senha, confirmacao):
    if not bcrypt.checkpw(
        (senha_atual or "").encode("utf-8"), usuario.senha_hash.encode("utf-8")
    ):
        raise ContaError("Senha atual incorreta.", campo="senha_atual")

    nova_senha = nova_senha or ""
    if len(nova_senha) < SENHA_MIN_LENGTH:
        raise ContaError(
            f"A nova senha deve ter pelo menos {SENHA_MIN_LENGTH} caracteres.",
            campo="nova_senha",
        )
    if nova_senha != (confirmacao or ""):
        raise ContaError("A confirmação da senha não confere.", campo="confirmacao")
    if nova_senha == senha_atual:
        raise ContaError(
            "A nova senha deve ser diferente da atual.", campo="nova_senha"
        )

    usuario.senha_hash = bcrypt.hashpw(
        nova_senha.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    db.session.commit()


# ------------------------------------------------------------- Preferências

def obter_preferencias(usuario):
    """Padrão + o que o usuário salvou (valores inválidos/antigos ignorados)."""
    preferencias = dict(PREFERENCIAS_PADRAO)
    salvas = usuario.preferencias or {}
    for chave, padrao in PREFERENCIAS_PADRAO.items():
        valor = salvas.get(chave, padrao)
        if isinstance(valor, type(padrao)) and (
            chave != "formato_hora" or valor in FORMATOS_HORA
        ):
            preferencias[chave] = valor
    return preferencias


def _gravar(usuario, novas):
    # Novo dict (não mutação in-place) pro SQLAlchemy detectar a mudança no JSON.
    usuario.preferencias = {**obter_preferencias(usuario), **novas}
    db.session.commit()


def salvar_preferencias(usuario, dados):
    """Formulário da tela Preferências. Checkbox desmarcado não vem no POST,
    então ausente = desligado. Só grava as que fazem sentido pro papel."""
    formato = dados.get("formato_hora")
    if formato not in FORMATOS_HORA:
        raise ContaError("Formato de hora inválido.", campo="formato_hora")

    novas = {
        "menu_recolhido": dados.get("menu_recolhido") == "on",
        "formato_hora": formato,
    }
    # Admin não participa de chat (RN-016) nem recebe emergência.
    if usuario.papel in (PapelEnum.socorrista, PapelEnum.hospital):
        novas["som_chat"] = dados.get("som_chat") == "on"
    if usuario.papel == PapelEnum.hospital:
        novas["som_nova_emergencia"] = dados.get("som_nova_emergencia") == "on"
    _gravar(usuario, novas)


def salvar_menu_recolhido(usuario, recolhido):
    """Botão de recolher do próprio menu: mesma preferência da tela."""
    _gravar(usuario, {"menu_recolhido": bool(recolhido)})
