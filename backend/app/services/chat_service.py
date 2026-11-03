"""HU-018/HU-019: chat entre o socorrista dono e o hospital destino de uma
ocorrência. RN-016 (só a dupla da ocorrência, admin bloqueado) reaproveita
a mesma checagem de acesso do rastreamento em tempo real — a regra de quem
pode "ver" uma ocorrência é idêntica à de quem pode conversar sobre ela.
"""

from datetime import datetime

from app import db
from app.models.mensagem import Mensagem
from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum
from app.models.usuario import PapelEnum
from app.services import ocorrencia_service

MENSAGEM_CHAT_ENCERRADO = "Esta conversa foi encerrada."
MENSAGEM_CONTEUDO_VAZIO = "A mensagem não pode estar vazia."


class ChatError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def enviar_mensagem(ocorrencia_id, conteudo, usuario_atual):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    # RN-016: mesma dupla socorrista-dono/hospital-destino do rastreamento;
    # admin nunca bate em nenhuma das duas condições, então já fica de fora.
    ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, usuario_atual)

    # RN-022: trava tanto pra quem já tinha a aba aberta quando a ocorrência
    # foi finalizada quanto pra qualquer tentativa direta via WebSocket.
    if ocorrencia.chat_encerrado_em is not None:
        raise ChatError(MENSAGEM_CHAT_ENCERRADO)

    conteudo = (conteudo or "").strip()
    if not conteudo:
        raise ChatError(MENSAGEM_CONTEUDO_VAZIO)

    mensagem = Mensagem(
        ocorrencia_id=ocorrencia.id, remetente_id=usuario_atual.id, conteudo=conteudo
    )
    db.session.add(mensagem)
    db.session.commit()
    return mensagem


def listar_mensagens(ocorrencia_id, usuario_atual):
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, usuario_atual)
    return ocorrencia.mensagens, ocorrencia.chat_encerrado_em is not None


def encerrar_chat(ocorrencia):
    """RN-022: chamada de dentro de finalizar_ocorrencia(), na MESMA
    transação — não comita aqui, quem chama decide quando persistir."""
    ocorrencia.chat_encerrado_em = datetime.utcnow()


def listar_conversas(usuario_atual):
    """Inbox = HISTÓRICO: só conversas de ocorrências já finalizadas (a
    conversa de uma emergência em andamento acontece na própria tela da
    ocorrência). Uma por ocorrência em que o usuário é a dupla (socorrista
    dono ou hospital destino), mais recente primeiro. Título mostra o nome
    da outra parte + o número da ocorrência, pra desambiguar quando a mesma
    pessoa aparece em mais de uma."""
    finalizada = Ocorrencia.status == StatusOcorrenciaEnum.finalizada
    if usuario_atual.papel == PapelEnum.socorrista and usuario_atual.socorrista:
        ocorrencias = Ocorrencia.query.filter(
            Ocorrencia.socorrista_id == usuario_atual.socorrista.id,
            Ocorrencia.hospital_id.isnot(None),
            finalizada,
        ).all()
    elif usuario_atual.papel == PapelEnum.hospital and usuario_atual.hospital:
        ocorrencias = Ocorrencia.query.filter(
            Ocorrencia.hospital_id == usuario_atual.hospital.id, finalizada
        ).all()
    else:
        # RN-016: admin (ou qualquer papel sem vínculo) nunca vê conversa
        # nenhuma — lista vazia, sem precisar de um bloqueio explícito.
        ocorrencias = []

    conversas = []
    for ocorrencia in ocorrencias:
        ultima = ocorrencia.mensagens[-1] if ocorrencia.mensagens else None
        nao_lidas = sum(
            1 for m in ocorrencia.mensagens
            if not m.lida and m.remetente_id != usuario_atual.id
        )
        outro_nome = (
            ocorrencia.hospital.nome
            if usuario_atual.papel == PapelEnum.socorrista
            else ocorrencia.socorrista.usuario.nome
        )
        conversas.append(
            {
                "ocorrencia_id": ocorrencia.id,
                "titulo": f"{outro_nome} — Ocorrência #{ocorrencia.id}",
                "ultima_mensagem": ultima.conteudo if ultima else None,
                "ultima_em": ultima.enviado_em if ultima else ocorrencia.criado_em,
                "nao_lidas": nao_lidas,
            }
        )

    conversas.sort(key=lambda c: c["ultima_em"], reverse=True)
    return conversas


def contar_nao_lidas(usuario_atual):
    """Total de mensagens não lidas em todas as conversas do Inbox — usado
    pro badge no sidebar. Uma query de contagem, sem montar a lista inteira."""
    base = Mensagem.query.join(Ocorrencia).filter(
        Mensagem.lida.is_(False),
        Mensagem.remetente_id != usuario_atual.id,
        Ocorrencia.status == StatusOcorrenciaEnum.finalizada,
    )
    if usuario_atual.papel == PapelEnum.socorrista and usuario_atual.socorrista:
        return base.filter(Ocorrencia.socorrista_id == usuario_atual.socorrista.id).count()
    if usuario_atual.papel == PapelEnum.hospital and usuario_atual.hospital:
        return base.filter(Ocorrencia.hospital_id == usuario_atual.hospital.id).count()
    return 0


def marcar_como_lidas(ocorrencia_id, usuario_atual):
    """Abrir a conversa marca como lidas as mensagens que o outro lado
    mandou — não mexe nas que o próprio usuário enviou (o check-check de
    'lida' nelas reflete o outro lado ter aberto, não isto aqui)."""
    ocorrencia = ocorrencia_service.obter_ocorrencia(ocorrencia_id)
    ocorrencia_service.verificar_acesso_leitura_ocorrencia(ocorrencia, usuario_atual)

    mudou = False
    for mensagem in ocorrencia.mensagens:
        if not mensagem.lida and mensagem.remetente_id != usuario_atual.id:
            mensagem.lida = True
            mudou = True
    if mudou:
        db.session.commit()


# TODO (ADM-03/HU-019 "histórico de administrador"): quando existir uma
# tela de admin pra auditar conversas entre socorrista e hospital, ela vai
# precisar de uma função separada aqui que NÃO usa
# verificar_acesso_leitura_ocorrencia (que bloqueia admin de propósito,
# RN-016) — provavelmente algo como `listar_mensagens_admin(ocorrencia_id)`
# sem checagem de dono/destino, só a checagem de papel=admin no controller.
