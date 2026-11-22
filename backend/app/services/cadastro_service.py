import bcrypt
from flask import abort
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.auditoria import Auditoria, EntidadeAuditoriaEnum, TipoOperacaoEnum
from app.models.hospital import Hospital
from app.models.socorrista import Socorrista
from app.models.usuario import PapelEnum, Usuario
from app.services import nominatim_client

# Decisão de v1: senha mínima de 6 caracteres nos cadastros feitos pelo admin.
SENHA_MIN_LENGTH = 6

MENSAGEM_EMAIL_DUPLICADO = "E-mail já cadastrado."


class CadastroError(Exception):
    def __init__(self, message, campo=None):
        self.message = message
        self.campo = campo
        super().__init__(message)


# Tamanho das colunas no banco: acima disso o PostgreSQL recusaria o INSERT
# com erro 500; aqui vira uma mensagem no formulário.
TAMANHO_MAXIMO = {
    "nome": (150, "nome"),
    "email": (150, "e-mail"),
    "endereco": (255, "endereço"),
    "responsavel_nome": (150, "nome do responsável"),
    "matricula": (50, "matrícula"),
    "telefone": (30, "telefone"),
}


def _validar_tamanhos(dados):
    for campo, (limite, rotulo) in TAMANHO_MAXIMO.items():
        if len((dados.get(campo) or "").strip()) > limite:
            raise CadastroError(f"O campo {rotulo} aceita no máximo {limite} caracteres.", campo=campo)


def _hash_senha(senha):
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _resolver_coordenadas(dados, endereco, endereco_mudou, latitude_atual=None, longitude_atual=None):
    """Prioriza a lat/long confirmada no mapa do formulário (o admin viu o
    pino e, se precisou, arrastou pra corrigir) sobre a geocodificação
    automática do endereço em texto — o Nominatim não acha vários endereços
    reais (ex: quadras de Brasília), então depender só dele deixava o
    hospital sem posição sempre que isso acontecia."""
    lat_raw = (dados.get("latitude") or "").strip()
    lng_raw = (dados.get("longitude") or "").strip()
    if lat_raw and lng_raw:
        try:
            return float(lat_raw), float(lng_raw)
        except ValueError:
            pass

    # Sem lat/long confirmada (ex: JS desabilitado) — cai pro geocode
    # automático como antes, só quando o endereço muda (a API pública do
    # Nominatim tem limite de requisições por segundo).
    if endereco_mudou:
        coordenadas = nominatim_client.geocodificar_endereco(endereco)
        return (coordenadas[0], coordenadas[1]) if coordenadas else (None, None)

    return latitude_atual, longitude_atual


def _normalizar_telefone(valor):
    """Opcional. Guarda como digitado (só tira espaços nas pontas); vazio vira None."""
    return (valor or "").strip() or None


def _validar_email(email, campo="email"):
    if not email:
        raise CadastroError("O campo e-mail é obrigatório.", campo=campo)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise CadastroError("E-mail inválido.", campo=campo)


def _validar_senha(senha, obrigatoria):
    if not senha:
        if obrigatoria:
            raise CadastroError("O campo senha é obrigatório.", campo="senha")
        return
    if len(senha) < SENHA_MIN_LENGTH:
        raise CadastroError(
            f"A senha deve ter pelo menos {SENHA_MIN_LENGTH} caracteres.", campo="senha"
        )


def _verificar_email_disponivel(email, ignorar_usuario_id=None):
    query = Usuario.query.filter_by(email=email)
    if ignorar_usuario_id is not None:
        query = query.filter(Usuario.id != ignorar_usuario_id)
    if query.first() is not None:
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")


def _registrar_auditoria(tipo_operacao, entidade_tipo, entidade_id, admin_atual):
    db.session.add(
        Auditoria(
            tipo_operacao=tipo_operacao,
            entidade_tipo=entidade_tipo,
            entidade_id=entidade_id,
            admin_id=admin_atual.id,
        )
    )


# --------------------------------------------------------------- Hospitais

def listar_hospitais():
    return Hospital.query.order_by(Hospital.nome).all()


def obter_hospital(hospital_id):
    return Hospital.query.get_or_404(hospital_id)


def criar_hospital(dados, admin_atual):
    _validar_tamanhos(dados)
    nome = (dados.get("nome") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    tem_heliponto = dados.get("tem_heliponto") == "on"
    tem_garagem = dados.get("tem_garagem") == "on"
    capacidade_raw = (dados.get("capacidade_maxima") or "").strip()
    responsavel_nome = (dados.get("responsavel_nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome:
        raise CadastroError("O campo nome do hospital é obrigatório.", campo="nome")
    if not endereco:
        raise CadastroError("O campo endereço é obrigatório.", campo="endereco")
    if not responsavel_nome:
        raise CadastroError(
            "O campo nome do responsável é obrigatório.", campo="responsavel_nome"
        )

    capacidade_maxima = _validar_capacidade_maxima(capacidade_raw)

    _validar_email(email)
    _validar_senha(senha, obrigatoria=True)
    _verificar_email_disponivel(email)

    try:
        usuario = Usuario(
            nome=responsavel_nome,
            email=email,
            senha_hash=_hash_senha(senha),
            papel=PapelEnum.hospital,
            ativo=True,
        )
        db.session.add(usuario)
        db.session.flush()

        latitude, longitude = _resolver_coordenadas(dados, endereco, endereco_mudou=True)

        # RN-002: hospital.usuario_id é único (um usuário-hospital por
        # hospital) — já garantido pelo schema, pois este usuário é criado
        # exclusivamente para este hospital nesta mesma transação.
        hospital = Hospital(
            nome=nome,
            endereco=endereco,
            tem_heliponto=tem_heliponto,
            tem_garagem=tem_garagem,
            capacidade_maxima=capacidade_maxima,
            ativo=True,
            usuario_id=usuario.id,
            latitude=latitude,
            longitude=longitude,
        )
        db.session.add(hospital)
        db.session.flush()

        _registrar_auditoria(
            TipoOperacaoEnum.criacao, EntidadeAuditoriaEnum.hospital, hospital.id, admin_atual
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")

    return hospital


def editar_hospital(hospital_id, dados, admin_atual):
    hospital = obter_hospital(hospital_id)
    usuario = hospital.usuario

    _validar_tamanhos(dados)
    nome = (dados.get("nome") or "").strip()
    endereco = (dados.get("endereco") or "").strip()
    tem_heliponto = dados.get("tem_heliponto") == "on"
    tem_garagem = dados.get("tem_garagem") == "on"
    capacidade_raw = (dados.get("capacidade_maxima") or "").strip()
    responsavel_nome = (dados.get("responsavel_nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome:
        raise CadastroError("O campo nome do hospital é obrigatório.", campo="nome")
    if not endereco:
        raise CadastroError("O campo endereço é obrigatório.", campo="endereco")
    if not responsavel_nome:
        raise CadastroError(
            "O campo nome do responsável é obrigatório.", campo="responsavel_nome"
        )

    capacidade_maxima = _validar_capacidade_maxima(capacidade_raw)

    _validar_email(email)
    _validar_senha(senha, obrigatoria=False)
    _verificar_email_disponivel(email, ignorar_usuario_id=usuario.id)

    try:
        usuario.nome = responsavel_nome
        usuario.email = email
        if senha:
            usuario.senha_hash = _hash_senha(senha)

        hospital.latitude, hospital.longitude = _resolver_coordenadas(
            dados,
            endereco,
            endereco_mudou=(endereco != hospital.endereco),
            latitude_atual=hospital.latitude,
            longitude_atual=hospital.longitude,
        )

        hospital.nome = nome
        hospital.endereco = endereco
        hospital.tem_heliponto = tem_heliponto
        hospital.tem_garagem = tem_garagem
        hospital.capacidade_maxima = capacidade_maxima

        _registrar_auditoria(
            TipoOperacaoEnum.edicao, EntidadeAuditoriaEnum.hospital, hospital.id, admin_atual
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")

    return hospital


def alternar_status_hospital(hospital_id, admin_atual):
    hospital = obter_hospital(hospital_id)
    hospital.ativo = not hospital.ativo

    # RN-015: ao desativar, o login do usuário vinculado passa a ser
    # bloqueado (checagem feita em auth_service a partir de hospital.ativo).
    tipo = TipoOperacaoEnum.desativacao if not hospital.ativo else TipoOperacaoEnum.edicao
    _registrar_auditoria(tipo, EntidadeAuditoriaEnum.hospital, hospital.id, admin_atual)
    db.session.commit()
    return hospital


def _validar_capacidade_maxima(capacidade_raw):
    if not capacidade_raw:
        return None
    # isascii(): "²" passa em isdigit() mas não em int(). Zero seria lido como
    # "sem limite" pela RN-006, então também é recusado.
    if not (capacidade_raw.isascii() and capacidade_raw.isdigit()) or int(capacidade_raw) < 1:
        raise CadastroError(
            "Capacidade máxima deve ser um número inteiro positivo.",
            campo="capacidade_maxima",
        )
    if int(capacidade_raw) > 10000:
        raise CadastroError("Capacidade máxima deve ser de no máximo 10000 leitos.", campo="capacidade_maxima")
    return int(capacidade_raw)


# ------------------------------------------------------------- Socorristas

def listar_socorristas():
    # contas temporárias do modo demonstração não são equipe: ficam fora do cadastro
    from app.services.demo_service import DOMINIO_VISITANTE

    return (
        Socorrista.query.join(Usuario)
        .filter(~Usuario.email.like(f"%{DOMINIO_VISITANTE}"))
        .order_by(Usuario.nome)
        .all()
    )


def obter_socorrista(socorrista_id):
    return Socorrista.query.get_or_404(socorrista_id)


def criar_socorrista(dados, admin_atual):
    _validar_tamanhos(dados)
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""
    matricula = (dados.get("matricula") or "").strip()
    telefone = _normalizar_telefone(dados.get("telefone"))

    if not nome:
        raise CadastroError("O campo nome é obrigatório.", campo="nome")
    if not matricula:
        raise CadastroError("O campo matrícula é obrigatório.", campo="matricula")

    _validar_email(email)
    _validar_senha(senha, obrigatoria=True)
    _verificar_email_disponivel(email)
    _verificar_matricula_disponivel(matricula)

    try:
        usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=_hash_senha(senha),
            papel=PapelEnum.socorrista,
            ativo=True,
        )
        db.session.add(usuario)
        db.session.flush()

        socorrista = Socorrista(usuario_id=usuario.id, matricula=matricula, telefone=telefone)
        db.session.add(socorrista)
        db.session.flush()

        _registrar_auditoria(
            TipoOperacaoEnum.criacao, EntidadeAuditoriaEnum.socorrista, socorrista.id, admin_atual
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")

    return socorrista


def editar_socorrista(socorrista_id, dados, admin_atual):
    socorrista = obter_socorrista(socorrista_id)
    usuario = socorrista.usuario

    _validar_tamanhos(dados)
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""
    matricula = (dados.get("matricula") or "").strip()
    telefone = _normalizar_telefone(dados.get("telefone"))

    if not nome:
        raise CadastroError("O campo nome é obrigatório.", campo="nome")
    if not matricula:
        raise CadastroError("O campo matrícula é obrigatório.", campo="matricula")

    _validar_email(email)
    _validar_senha(senha, obrigatoria=False)
    _verificar_email_disponivel(email, ignorar_usuario_id=usuario.id)
    _verificar_matricula_disponivel(matricula, ignorar_socorrista_id=socorrista.id)

    try:
        usuario.nome = nome
        usuario.email = email
        if senha:
            usuario.senha_hash = _hash_senha(senha)
        socorrista.matricula = matricula
        socorrista.telefone = telefone

        _registrar_auditoria(
            TipoOperacaoEnum.edicao, EntidadeAuditoriaEnum.socorrista, socorrista.id, admin_atual
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")

    return socorrista


def alternar_status_socorrista(socorrista_id, admin_atual):
    socorrista = obter_socorrista(socorrista_id)
    usuario = socorrista.usuario
    usuario.ativo = not usuario.ativo

    # RN-014: socorrista inativo ainda consegue logar; o toggle aqui só
    # marca o status, a trava operacional é feita no módulo de ocorrências.
    tipo = TipoOperacaoEnum.desativacao if not usuario.ativo else TipoOperacaoEnum.edicao
    _registrar_auditoria(tipo, EntidadeAuditoriaEnum.socorrista, socorrista.id, admin_atual)
    db.session.commit()
    return socorrista


def _verificar_matricula_disponivel(matricula, ignorar_socorrista_id=None):
    query = Socorrista.query.filter_by(matricula=matricula)
    if ignorar_socorrista_id is not None:
        query = query.filter(Socorrista.id != ignorar_socorrista_id)
    if query.first() is not None:
        raise CadastroError("Matrícula já cadastrada.", campo="matricula")


# ------------------------------------------------------------------ Admins

def listar_admins():
    return Usuario.query.filter_by(papel=PapelEnum.admin).order_by(Usuario.nome).all()


def obter_admin(admin_id):
    admin = Usuario.query.filter_by(id=admin_id, papel=PapelEnum.admin).first()
    if admin is None:
        abort(404)
    return admin


def _contar_admins_ativos(ignorar_id=None):
    query = Usuario.query.filter_by(papel=PapelEnum.admin, ativo=True)
    if ignorar_id is not None:
        query = query.filter(Usuario.id != ignorar_id)
    return query.count()


def criar_admin(dados, admin_atual):
    _validar_tamanhos(dados)
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome:
        raise CadastroError("O campo nome é obrigatório.", campo="nome")

    _validar_email(email)
    _validar_senha(senha, obrigatoria=True)
    _verificar_email_disponivel(email)

    try:
        # RN-018: sem limite de admins ativos.
        admin = Usuario(
            nome=nome,
            email=email,
            senha_hash=_hash_senha(senha),
            papel=PapelEnum.admin,
            ativo=True,
        )
        db.session.add(admin)
        db.session.flush()

        _registrar_auditoria(TipoOperacaoEnum.criacao, EntidadeAuditoriaEnum.admin, admin.id, admin_atual)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")

    return admin


def editar_admin(admin_id, dados, admin_atual):
    admin = obter_admin(admin_id)

    _validar_tamanhos(dados)
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome:
        raise CadastroError("O campo nome é obrigatório.", campo="nome")

    _validar_email(email)
    _validar_senha(senha, obrigatoria=False)
    _verificar_email_disponivel(email, ignorar_usuario_id=admin.id)

    try:
        admin.nome = nome
        admin.email = email
        if senha:
            admin.senha_hash = _hash_senha(senha)

        _registrar_auditoria(TipoOperacaoEnum.edicao, EntidadeAuditoriaEnum.admin, admin.id, admin_atual)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CadastroError(MENSAGEM_EMAIL_DUPLICADO, campo="email")

    return admin


def alternar_status_admin(admin_id, admin_atual):
    admin = obter_admin(admin_id)

    # RN-020: não pode desativar o último admin ativo do sistema.
    if admin.ativo and _contar_admins_ativos(ignorar_id=admin.id) == 0:
        raise CadastroError(
            "Não é possível desativar: este é o último admin ativo do sistema."
        )

    admin.ativo = not admin.ativo
    tipo = TipoOperacaoEnum.desativacao if not admin.ativo else TipoOperacaoEnum.edicao
    _registrar_auditoria(tipo, EntidadeAuditoriaEnum.admin, admin.id, admin_atual)
    db.session.commit()
    return admin


def excluir_admin(admin_id, admin_atual):
    admin = obter_admin(admin_id)

    # RN-020: não pode excluir o último admin ativo do sistema.
    if admin.ativo and _contar_admins_ativos(ignorar_id=admin.id) == 0:
        raise CadastroError(
            "Não é possível excluir: este é o último admin ativo do sistema."
        )

    admin_id_excluido = admin.id
    db.session.delete(admin)
    _registrar_auditoria(
        TipoOperacaoEnum.exclusao, EntidadeAuditoriaEnum.admin, admin_id_excluido, admin_atual
    )
    db.session.commit()
