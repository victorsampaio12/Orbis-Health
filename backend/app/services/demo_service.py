"""Modo demonstração (apresentação do TCC): quem escaneia o QR code entra
como socorrista sem cadastro nem senha e faz o fluxo inteiro pelo celular.

- Cada visitante ganha uma conta de socorrista própria e descartável, então
  as emergências de um não se misturam com as de outro (e a regra de "uma
  ocorrência ativa por socorrista" continua valendo para cada um).
- O trajeto até o hospital é encurtado (a pessoa está parada na plateia).
- O hospital responde sozinho no chat, para ninguém ficar sem resposta.
- Visitante não envia fotos (o link é público e o painel pode estar no telão).
- Contas de visitante e tudo o que elas criaram somem depois de 24 h.

Só funciona com MODO_DEMONSTRACAO=1 no .env; desligado, nada disto existe.
"""

import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta

import bcrypt
from flask import current_app

from app import db, socketio
from app.models.mensagem import Mensagem
from app.models.ocorrencia import Ocorrencia
from app.models.paciente import Paciente
from app.models.socorrista import Socorrista
from app.models.usuario import PapelEnum, Usuario

# Domínio reservado (.invalid nunca existe na internet): identifica a conta
# de visitante sem precisar de coluna nova no banco.
DOMINIO_VISITANTE = "@visitante.invalid"
VALIDADE_HORAS = 24

# Trajeto de demonstração: curto o bastante para ver chegar, longo o
# bastante para acompanhar a viatura no mapa.
DURACAO_TRAJETO_MIN_S = 60
DURACAO_TRAJETO_MAX_S = 150

# Freio contra abuso do link público. Numa apresentação, a plateia inteira
# costuma sair pelo mesmo IP (Wi-Fi do local), então o limite por IP é alto.
LIMITE_POR_IP_HORA = 150
LIMITE_VISITANTES_ATIVOS = 600

MENSAGEM_LIMITE = "Muitos acessos de demonstração agora. Tente de novo em alguns minutos."

RESPOSTAS_HOSPITAL = [
    "Aqui é a regulação do {hospital}. Recebemos o seu chamado e a equipe já está se preparando.",
    "Entendido. Sala de emergência reservada para o paciente.",
    "Estamos acompanhando a viatura em tempo real. Pode trazer.",
    "Recebido, obrigado pela atualização.",
]
ATRASO_RESPOSTA_S = 2.5
INTERVALO_MIN_RESPOSTA_S = 8

_acessos_por_ip = {}
_lock = threading.Lock()
_ultima_limpeza = 0.0


class DemoError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def ativo():
    return bool(current_app.config.get("MODO_DEMONSTRACAO"))


def eh_visitante(usuario):
    email = getattr(usuario, "email", None) or ""
    return email.endswith(DOMINIO_VISITANTE)


# ------------------------------------------------------------------ entrada

def _registrar_acesso(ip):
    agora = time.monotonic()
    with _lock:
        fila = _acessos_por_ip.setdefault(ip or "?", deque())
        while fila and agora - fila[0] > 3600:
            fila.popleft()
        if len(fila) >= LIMITE_POR_IP_HORA:
            raise DemoError(MENSAGEM_LIMITE)
        fila.append(agora)


def criar_visitante(ip):
    """Conta de socorrista descartável, sem senha conhecida por ninguém."""
    limpar_expirados_se_preciso()
    _registrar_acesso(ip)
    ativos = Usuario.query.filter(Usuario.email.like(f"%{DOMINIO_VISITANTE}")).count()
    if ativos >= LIMITE_VISITANTES_ATIVOS:
        raise DemoError(MENSAGEM_LIMITE)

    codigo = secrets.token_hex(4)
    numero = int(codigo[:4], 16) % 10000
    senha_hash = bcrypt.hashpw(secrets.token_bytes(24), bcrypt.gensalt(rounds=8)).decode()
    usuario = Usuario(
        nome=f"Visitante {numero:04d}",
        email=f"visitante-{codigo}{DOMINIO_VISITANTE}",
        senha_hash=senha_hash,
        papel=PapelEnum.socorrista,
        ativo=True,
    )
    db.session.add(usuario)
    db.session.flush()
    db.session.add(Socorrista(usuario_id=usuario.id, matricula=f"DEMO-{codigo.upper()}"))
    db.session.commit()
    return usuario


# ------------------------------------------------------------------ trajeto

def duracao_trajeto(duracao_s, usuario):
    if not eh_visitante(usuario):
        return duracao_s
    return max(DURACAO_TRAJETO_MIN_S, min(DURACAO_TRAJETO_MAX_S, duracao_s))


# --------------------------------------------------------------------- chat

def agendar_resposta_do_hospital(ocorrencia_id, remetente):
    """Depois da mensagem de um visitante, o hospital de destino responde."""
    if not eh_visitante(remetente):
        return
    socketio.start_background_task(
        _responder, current_app._get_current_object(), ocorrencia_id
    )


def _responder(app, ocorrencia_id):
    socketio.sleep(ATRASO_RESPOSTA_S)
    with app.app_context():
        try:
            ocorrencia = db.session.get(Ocorrencia, ocorrencia_id)
            if (
                ocorrencia is None
                or ocorrencia.chat_encerrado_em is not None
                or ocorrencia.hospital is None
                or ocorrencia.hospital.usuario is None
            ):
                return
            hospital_usuario = ocorrencia.hospital.usuario
            do_hospital = (
                Mensagem.query.filter_by(ocorrencia_id=ocorrencia.id, remetente_id=hospital_usuario.id)
                .order_by(Mensagem.enviado_em.desc())
                .all()
            )
            if do_hospital and (datetime.utcnow() - do_hospital[0].enviado_em).total_seconds() < INTERVALO_MIN_RESPOSTA_S:
                return
            texto = RESPOSTAS_HOSPITAL[min(len(do_hospital), len(RESPOSTAS_HOSPITAL) - 1)]
            mensagem = Mensagem(
                ocorrencia_id=ocorrencia.id,
                remetente_id=hospital_usuario.id,
                conteudo=texto.format(hospital=ocorrencia.hospital.nome),
            )
            db.session.add(mensagem)
            db.session.commit()
            socketio.emit(
                "mensagem_recebida",
                {
                    "id": mensagem.id,
                    "ocorrencia_id": mensagem.ocorrencia_id,
                    "remetente_id": mensagem.remetente_id,
                    "remetente_nome": hospital_usuario.nome,
                    "conteudo": mensagem.conteudo,
                    "enviado_em": mensagem.enviado_em.isoformat(),
                },
                room=f"ocorrencia_{ocorrencia.id}",
            )
        finally:
            db.session.remove()


# ------------------------------------------------------------------ limpeza

def limpar_expirados_se_preciso():
    """No máximo uma limpeza a cada 10 min, puxada pelos próprios acessos."""
    global _ultima_limpeza
    agora = time.monotonic()
    with _lock:
        if agora - _ultima_limpeza < 600:
            return 0
        _ultima_limpeza = agora
    return limpar_expirados()


def limpar_expirados(horas=VALIDADE_HORAS):
    """Apaga as contas de visitante mais antigas que `horas` e tudo o que
    elas criaram (ocorrências, pacientes, mensagens). Devolve quantas."""
    from app.services import anexo_service

    limite = datetime.utcnow() - timedelta(hours=horas)
    usuarios = Usuario.query.filter(
        Usuario.email.like(f"%{DOMINIO_VISITANTE}"), Usuario.criado_em < limite
    ).all()
    if not usuarios:
        return 0
    arquivos = []
    socorristas = [u.socorrista.id for u in usuarios if u.socorrista is not None]
    ocorrencias = [
        o.id for o in Ocorrencia.query.filter(Ocorrencia.socorrista_id.in_(socorristas)).all()
    ] if socorristas else []
    if ocorrencias:
        pacientes = Paciente.query.filter(Paciente.ocorrencia_id.in_(ocorrencias)).all()
        arquivos = [a.arquivo for p in pacientes for a in p.anexos]
        Mensagem.query.filter(Mensagem.ocorrencia_id.in_(ocorrencias)).delete(synchronize_session=False)
        for p in pacientes:
            db.session.delete(p)
        Ocorrencia.query.filter(Ocorrencia.id.in_(ocorrencias)).delete(synchronize_session=False)
    for u in usuarios:
        if u.socorrista is not None:
            db.session.delete(u.socorrista)
        db.session.delete(u)
    db.session.commit()
    anexo_service.apagar_arquivos(arquivos)   # só depois de o banco confirmar
    return len(usuarios)
