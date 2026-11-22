import math
from datetime import datetime

from flask import abort

from app import db
from app.models.auditoria import Auditoria, EntidadeAuditoriaEnum, TipoOperacaoEnum
from app.models.hospital import Hospital
from app.models.ocorrencia import (
    Ocorrencia,
    StatusOcorrenciaEnum,
    TipoRotaEnum,
    VeiculoEnum,
)
from app.models.paciente import REGIOES_LESAO, Paciente, PrioridadeEnum
from app.models.usuario import PapelEnum
from app.services import anexo_service, rota_service
from app.services.anexo_service import AnexoError

MENSAGEM_SOCORRISTA_INATIVO = "Socorrista inativo não pode operar"
MENSAGEM_HOSPITAL_INCOMPATIVEL = "Hospital Inválido — Tipo de Veículo Incompatível"
MENSAGEM_HOSPITAL_LOTADO = "Hospital selecionado lotado!"
MENSAGEM_ACESSO_NAO_AUTORIZADO = "Acesso não autorizado"
MENSAGEM_PRONTUARIO_INVALIDO = "Dados de prontuário inválidos!"
MENSAGEM_CHEGADA_NAO_CONFIRMADA = (
    "Não foi possível notificar chegada, por favor se dirija ao hospital destino!"
)
MENSAGEM_FINALIZAR_SEM_CHEGADA = (
    "Não foi possível finalizar ocorrência, por favor se dirija ao hospital destino!"
)
MENSAGEM_OCORRENCIA_ENCERRADA = "Esta ocorrência já foi finalizada e não pode mais ser alterada."
MENSAGEM_HOSPITAL_JA_ESCOLHIDO = (
    "Esta ocorrência já tem hospital de destino. Use \"Voltar\" para trocar antes de iniciar o trajeto."
)
MENSAGEM_COORDENADAS_INVALIDAS = "Coordenadas inválidas."
MENSAGEM_NAO_PODE_TROCAR_HOSPITAL = (
    "Não é possível trocar o hospital: o trajeto até ele já foi iniciado."
)

# RN-006: limiar de ocupação a partir do qual um hospital vira "crítico".
LIMIAR_CRITICO = 0.8


class OcorrenciaError(Exception):
    def __init__(self, message, campo=None):
        self.message = message
        self.campo = campo
        super().__init__(message)


class AcessoNaoAutorizadoError(Exception):
    def __init__(self, message=MENSAGEM_ACESSO_NAO_AUTORIZADO):
        self.message = message
        super().__init__(message)


def verificar_dono_ocorrencia(ocorrencia, usuario):
    """RN-008: só o socorrista que criou a ocorrência pode ver/escrever nas
    telas de gestão dela (pacientes, seleção de hospital)."""
    if (
        usuario.papel != PapelEnum.socorrista
        or usuario.socorrista is None
        or ocorrencia.socorrista_id != usuario.socorrista.id
    ):
        raise AcessoNaoAutorizadoError()


def verificar_acesso_leitura_ocorrencia(ocorrencia, usuario):
    """RN-007: só o socorrista dono ou o hospital destino podem ver."""
    if (
        usuario.papel == PapelEnum.socorrista
        and usuario.socorrista is not None
        and ocorrencia.socorrista_id == usuario.socorrista.id
    ):
        return
    if (
        usuario.papel == PapelEnum.hospital
        and usuario.hospital is not None
        and ocorrencia.hospital_id == usuario.hospital.id
    ):
        return
    raise AcessoNaoAutorizadoError()


def verificar_operacao(ocorrencia, usuario, *status_permitidos):
    """Ações que ALTERAM a ocorrência: além de ser o socorrista dono (RN-008),
    ele precisa estar ativo (RN-014) e a ocorrência precisa estar num status
    em que a ação faz sentido — o servidor não confia nos botões da tela."""
    verificar_dono_ocorrencia(ocorrencia, usuario)
    if not usuario.ativo:
        raise OcorrenciaError(MENSAGEM_SOCORRISTA_INATIVO)
    if status_permitidos and ocorrencia.status not in status_permitidos:
        if ocorrencia.status == StatusOcorrenciaEnum.finalizada:
            raise OcorrenciaError(MENSAGEM_OCORRENCIA_ENCERRADA)
        raise OcorrenciaError(MENSAGEM_HOSPITAL_JA_ESCOLHIDO)


ATIVAS = (StatusOcorrenciaEnum.aberta, StatusOcorrenciaEnum.em_transporte)


def coordenada_valida(lat, lng):
    """Latitude/longitude finitas e dentro do globo (recusa nan, inf, 999)."""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)) or abs(lat) > 90 or abs(lng) > 180:
        return None
    return lat, lng


# --------------------------------------------------------------- Ocorrência

def criar_ocorrencia(dados, usuario_atual):
    # RN-014: socorrista inativo não pode operar (login continua permitido,
    # isso só bloqueia a ação operacional).
    if not usuario_atual.ativo:
        raise OcorrenciaError(MENSAGEM_SOCORRISTA_INATIVO)

    local = (dados.get("local") or "").strip()
    veiculo_raw = dados.get("veiculo") or ""
    comentarios = (dados.get("comentarios") or "").strip() or None

    if not local:
        raise OcorrenciaError("O campo local é obrigatório.", campo="local")
    if len(local) > 255:
        raise OcorrenciaError("O campo local aceita no máximo 255 caracteres.", campo="local")

    try:
        veiculo = VeiculoEnum(veiculo_raw)
    except ValueError:
        raise OcorrenciaError("Selecione um veículo válido.", campo="veiculo")

    # HU-013: a localização vem do Geolocation API do navegador, capturada
    # na própria tela de criação. Opcional aqui — se a permissão for
    # negada, a ocorrência ainda é criada, só não vai poder gerar rota até
    # a localização ser capturada (retomado na tela de detalhe).
    coordenadas = coordenada_valida(dados.get("latitude"), dados.get("longitude"))
    latitude_atual, longitude_atual = coordenadas or (None, None)

    ocorrencia = Ocorrencia(
        socorrista_id=usuario_atual.socorrista.id,
        veiculo=veiculo,
        status=StatusOcorrenciaEnum.aberta,
        local=local,
        comentarios=comentarios,
        latitude_atual=latitude_atual,
        longitude_atual=longitude_atual,
    )
    db.session.add(ocorrencia)
    db.session.commit()
    return ocorrencia


def salvar_localizacao(ocorrencia_id, latitude, longitude, usuario_atual):
    """Usada tanto pelo retry HTTP (localização não capturada na criação)
    quanto pelo handler de WebSocket do HU-022 (posição em tempo real) —
    é a mesma operação nos dois casos: atualiza a posição e recalcula o
    ETA se já existir uma rota gerada."""
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual, *ATIVAS)
    coordenadas = coordenada_valida(latitude, longitude)
    if coordenadas is None:
        raise OcorrenciaError(MENSAGEM_COORDENADAS_INVALIDAS)

    ocorrencia.latitude_atual, ocorrencia.longitude_atual = coordenadas
    rota_service.recalcular_eta(ocorrencia)
    db.session.commit()
    return ocorrencia


def obter_ocorrencia(ocorrencia_id):
    return Ocorrencia.query.get_or_404(ocorrencia_id)


def obter_ocorrencia_ativa_do_socorrista(usuario):
    """Ocorrência aberta/em_transporte do socorrista logado, se houver.

    Usado pelo sidebar pra decidir qual conjunto de itens de menu mostrar.
    """
    if usuario.papel != PapelEnum.socorrista or usuario.socorrista is None:
        return None

    return (
        Ocorrencia.query.filter_by(socorrista_id=usuario.socorrista.id)
        .filter(
            Ocorrencia.status.in_(
                [StatusOcorrenciaEnum.aberta, StatusOcorrenciaEnum.em_transporte]
            )
        )
        .order_by(Ocorrencia.criado_em.desc())
        .first()
    )


def listar_ocorrencias_hospital(hospital):
    """RN-007: só ocorrências cujo hospital_id é este hospital."""
    return (
        Ocorrencia.query.filter_by(hospital_id=hospital.id)
        .order_by(Ocorrencia.criado_em.desc())
        .all()
    )


# ---------------------------------------------------------------- Paciente

def _calcular_prioridade(paciente):
    """RN-010: recalculada a cada criação/atualização, nesta ordem."""
    if paciente.parada_cardiorrespiratoria:
        return PrioridadeEnum.critica
    if paciente.glasgow is not None and paciente.glasgow < 8:
        return PrioridadeEnum.critica
    if paciente.saturacao_o2 is not None and paciente.saturacao_o2 < 90:
        return PrioridadeEnum.critica
    if paciente.agravamento_registrado:
        return PrioridadeEnum.alta
    return PrioridadeEnum.media


# Faixas fisiologicamente possíveis: fora delas é erro de digitação, e
# valores absurdos (ex.: saturação -5) mudariam a prioridade (RN-010).
FAIXAS = {
    "frequencia_cardiaca": (0, 350, "frequência cardíaca"),
    "frequencia_respiratoria": (0, 120, "frequência respiratória"),
    "saturacao_o2": (0, 100, "saturação de O₂"),
    "glasgow": (3, 15, "Glasgow"),
    "temperatura": (25, 45, "temperatura"),
}
# Tamanho máximo dos campos de texto curtos (o mesmo das colunas do banco).
TAMANHOS = {
    "nome": (150, "nome"),
    "cpf": (14, "CPF"),
    "idade": (20, "idade"),
    "pressao_arterial": (20, "pressão arterial"),
    "nivel_consciencia": (100, "nível de consciência"),
}


def _erro_campo(campo, detalhe):
    return OcorrenciaError(f"{MENSAGEM_PRONTUARIO_INVALIDO} {detalhe}", campo=campo)


def _texto(dados, campo):
    valor = (dados.get(campo) or "").strip()
    limite, rotulo = TAMANHOS[campo]
    if len(valor) > limite:
        raise _erro_campo(campo, f"O campo {rotulo} aceita no máximo {limite} caracteres.")
    return valor or None


def _numero(dados, campo, tipo):
    valor = (dados.get(campo) or "").strip()
    if not valor:
        return None
    minimo, maximo, rotulo = FAIXAS[campo]
    try:
        numero = tipo(valor.replace(",", ".") if tipo is float else valor)
    except ValueError:
        raise _erro_campo(campo, f"O campo {rotulo} precisa ser um número.")
    if not (math.isfinite(numero) and minimo <= numero <= maximo):
        raise _erro_campo(campo, f"O campo {rotulo} deve estar entre {minimo} e {maximo}.")
    return numero


def _regioes_lesao(dados):
    """Regiões marcadas no boneco 3D. Aceita o campo repetido do formulário
    (regioes_lesao=cabeca&regioes_lesao=torax) ou uma lista separada por
    vírgula (app). Códigos desconhecidos são ignorados; guarda na ordem
    canônica de REGIOES_LESAO."""
    if hasattr(dados, "getlist"):
        brutos = dados.getlist("regioes_lesao")
    else:
        valor = dados.get("regioes_lesao")
        brutos = valor if isinstance(valor, list) else [valor or ""]
    marcadas = {parte.strip() for bruto in brutos for parte in str(bruto).split(",")}
    validas = [codigo for codigo in REGIOES_LESAO if codigo in marcadas]
    return ",".join(validas) or None


def _preencher_paciente(paciente, dados):
    nome = _texto(dados, "nome") or ""
    motivo_chamado = (dados.get("motivo_chamado") or "").strip()

    if not nome:
        raise OcorrenciaError("O campo nome é obrigatório.", campo="nome")
    if not motivo_chamado:
        raise OcorrenciaError(
            "O campo motivo do chamado é obrigatório.", campo="motivo_chamado"
        )

    documentos_raw = dados.get("documentos_em_maos")
    documentos_em_maos = documentos_raw if documentos_raw in ("sim", "nao") else None

    paciente.nome = nome
    paciente.cpf = _texto(dados, "cpf")
    paciente.idade = _texto(dados, "idade")
    paciente.documentos_em_maos = (
        None if documentos_em_maos is None else documentos_em_maos == "sim"
    )
    paciente.motivo_chamado = motivo_chamado
    paciente.pressao_arterial = _texto(dados, "pressao_arterial")
    paciente.frequencia_cardiaca = _numero(dados, "frequencia_cardiaca", int)
    paciente.frequencia_respiratoria = _numero(dados, "frequencia_respiratoria", int)
    paciente.saturacao_o2 = _numero(dados, "saturacao_o2", int)
    paciente.temperatura = _numero(dados, "temperatura", float)
    paciente.nivel_consciencia = _texto(dados, "nivel_consciencia")
    paciente.glasgow = _numero(dados, "glasgow", int)
    paciente.estavel = dados.get("estavel") == "on"
    paciente.agravamento_registrado = dados.get("agravamento_registrado") == "on"
    paciente.melhorando = dados.get("melhorando") == "on"
    paciente.parada_cardiorrespiratoria = (
        dados.get("parada_cardiorrespiratoria") == "on"
    )
    paciente.observacao = (dados.get("observacao") or "").strip() or None
    paciente.diagnostico = (dados.get("diagnostico") or "").strip() or None
    paciente.regioes_lesao = _regioes_lesao(dados)

    paciente.prioridade = _calcular_prioridade(paciente)


def _processar_anexos(paciente, arquivos, remover_ids):
    """Valida as fotos novas antes de qualquer gravação; inválida = nada salvo."""
    try:
        preparadas = anexo_service.preparar(arquivos or [])
        anexo_service.verificar_quantidade(paciente, preparadas, removendo=len(remover_ids or []))
    except AnexoError as erro:
        db.session.rollback()
        raise OcorrenciaError(erro.message, campo="anexos")
    return preparadas


def _sem_fotos_de_visitante(usuario, arquivos):
    """Modo demonstração: o link é público, então visitante não envia fotos."""
    from app.services import demo_service

    return None if demo_service.eh_visitante(usuario) else arquivos


def adicionar_paciente(ocorrencia_id, dados, usuario_atual, arquivos=None):
    arquivos = _sem_fotos_de_visitante(usuario_atual, arquivos)
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual, *ATIVAS)

    paciente = Paciente(ocorrencia_id=ocorrencia.id)
    _preencher_paciente(paciente, dados)
    preparadas = _processar_anexos(None, arquivos, [])

    db.session.add(paciente)
    db.session.flush()
    anexo_service.gravar(paciente, preparadas, usuario_atual)
    db.session.commit()
    return paciente


def obter_paciente(ocorrencia_id, paciente_id):
    paciente = Paciente.query.get_or_404(paciente_id)
    if paciente.ocorrencia_id != int(ocorrencia_id):
        abort(404)
    return paciente


def atualizar_paciente(ocorrencia_id, paciente_id, dados, usuario_atual, arquivos=None, remover_ids=None):
    arquivos = _sem_fotos_de_visitante(usuario_atual, arquivos)
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual, *ATIVAS)

    paciente = obter_paciente(ocorrencia_id, paciente_id)
    preparadas = _processar_anexos(paciente, arquivos, remover_ids)
    try:
        _preencher_paciente(paciente, dados)
    except OcorrenciaError:
        db.session.rollback()
        raise
    # os arquivos das fotos removidas só saem do disco depois que o banco
    # confirmou — se algo falhar antes, a foto continua íntegra.
    arquivos_removidos = anexo_service.remover(paciente, remover_ids or [])
    anexo_service.gravar(paciente, preparadas, usuario_atual)
    db.session.commit()
    anexo_service.apagar_arquivos(arquivos_removidos)
    return paciente


def listar_pacientes_ordenados(ocorrencia):
    """RN-010: críticos primeiro, independente da ordem de cadastro."""
    ordem = {PrioridadeEnum.critica: 0, PrioridadeEnum.alta: 1, PrioridadeEnum.media: 2}
    return sorted(ocorrencia.pacientes, key=lambda p: (ordem[p.prioridade], p.criado_em))


# -------------------------------------------------------- Seleção hospital

def status_capacidade(hospital):
    """RN-006: disponível / crítico / lotado, a partir das ocorrências
    ativas (aberta ou em_transporte) vinculadas a este hospital."""
    ocorrencias_ativas = Ocorrencia.query.filter(
        Ocorrencia.hospital_id == hospital.id,
        Ocorrencia.status.in_(
            [StatusOcorrenciaEnum.aberta, StatusOcorrenciaEnum.em_transporte]
        ),
    ).count()

    capacidade = hospital.capacidade_maxima
    if not capacidade:
        return "disponivel", ocorrencias_ativas

    if ocorrencias_ativas >= capacidade:
        return "lotado", ocorrencias_ativas
    if ocorrencias_ativas >= capacidade * LIMIAR_CRITICO:
        return "critico", ocorrencias_ativas
    return "disponivel", ocorrencias_ativas


def listar_hospitais_disponiveis(ocorrencia):
    """RN-003: filtra por veículo (só hospitais ativos e compatíveis).
    RN-006: calcula o status de capacidade de cada um.

    Retorna lista de tuplas (hospital, status, ocorrencias_ativas). Um
    hospital "lotado" ainda aparece aqui (pra mostrar o motivo do bloqueio),
    mas a seleção dele é recusada em `selecionar_hospital`.
    """
    query = Hospital.query.filter_by(ativo=True)

    if ocorrencia.veiculo == VeiculoEnum.helicoptero:
        query = query.filter_by(tem_heliponto=True)
    else:
        query = query.filter_by(tem_garagem=True)

    hospitais = query.order_by(Hospital.nome).all()
    return [(h,) + status_capacidade(h) for h in hospitais]


def selecionar_hospital(ocorrencia_id, hospital_id, usuario_atual):
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual, StatusOcorrenciaEnum.aberta)

    try:
        hospital_id = int(hospital_id)
    except (TypeError, ValueError):
        abort(404)
    if not 0 < hospital_id < 2**31:
        abort(404)
    # Trava a linha do hospital até o commit: dois socorristas escolhendo o
    # mesmo hospital ao mesmo tempo passam por aqui um de cada vez, e o
    # segundo já conta a ocorrência do primeiro na checagem de lotação (RN-006).
    hospital = (
        db.session.query(Hospital).filter_by(id=hospital_id).with_for_update().first()
    )
    if hospital is None:
        abort(404)

    # RN-003 revalidada no servidor — não confia na lista exibida no GET.
    compativel = hospital.ativo and (
        (ocorrencia.veiculo == VeiculoEnum.helicoptero and hospital.tem_heliponto)
        or (ocorrencia.veiculo == VeiculoEnum.ambulancia and hospital.tem_garagem)
    )
    if not compativel:
        raise OcorrenciaError(MENSAGEM_HOSPITAL_INCOMPATIVEL)

    # RN-006 revalidada no servidor.
    status_cap, _ = status_capacidade(hospital)
    if status_cap == "lotado":
        raise OcorrenciaError(MENSAGEM_HOSPITAL_LOTADO)

    # RN-004/RN-005: uma única transação — hospital_id, status e tipo_rota
    # juntos, tipo_rota decidido pelo veículo, nunca pelo usuário.
    ocorrencia.hospital_id = hospital.id
    # Trava a posição do hospital agora (ver comentário no model) — edições
    # futuras no cadastro do hospital não afetam esta ocorrência.
    ocorrencia.destino_latitude = hospital.latitude
    ocorrencia.destino_longitude = hospital.longitude
    ocorrencia.status = StatusOcorrenciaEnum.em_transporte
    ocorrencia.tipo_rota = (
        TipoRotaEnum.linha_reta
        if ocorrencia.veiculo == VeiculoEnum.helicoptero
        else TipoRotaEnum.terrestre
    )
    db.session.commit()
    return ocorrencia


def desfazer_selecao_hospital(ocorrencia_id, usuario_atual):
    """Volta a ocorrência para "aberta" (sem hospital), para o socorrista
    escolher outro. Só vale enquanto o trajeto não começou. As mensagens do
    chat com o hospital abandonado são apagadas: a conversa é entre o
    socorrista e AQUELE hospital (RN-016) e não pode ficar visível para o
    próximo. Devolve o id do hospital anterior, para avisá-lo."""
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual)

    if (
        ocorrencia.status != StatusOcorrenciaEnum.em_transporte
        or ocorrencia.trajeto_iniciado_em is not None
        or ocorrencia.chegada_confirmada_em is not None
    ):
        raise OcorrenciaError(MENSAGEM_NAO_PODE_TROCAR_HOSPITAL)

    hospital_anterior_id = ocorrencia.hospital_id
    for mensagem in list(ocorrencia.mensagens):
        db.session.delete(mensagem)

    ocorrencia.hospital_id = None
    ocorrencia.destino_latitude = None
    ocorrencia.destino_longitude = None
    ocorrencia.tipo_rota = None
    ocorrencia.rota_geometria = None
    ocorrencia.rota_gerada_em = None
    ocorrencia.distancia_estimada_km = None
    ocorrencia.tempo_estimado_min = None
    ocorrencia.trajeto_duracao_s = None
    ocorrencia.status = StatusOcorrenciaEnum.aberta
    db.session.commit()
    return hospital_anterior_id


# ------------------------------------------------ Chegada e finalização

def marcar_chegada(ocorrencia_id, usuario_atual):
    """HU-021: só libera se a posição atual estiver dentro do raio de
    tolerância (RN, RAIO_CHEGADA_KM em rota_service) do hospital destino."""
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual)

    if ocorrencia.status != StatusOcorrenciaEnum.em_transporte:
        raise OcorrenciaError(MENSAGEM_CHEGADA_NAO_CONFIRMADA)

    distancia = rota_service.distancia_ate_hospital_km(ocorrencia)
    if distancia is None or distancia > rota_service.RAIO_CHEGADA_KM:
        raise OcorrenciaError(MENSAGEM_CHEGADA_NAO_CONFIRMADA)

    ocorrencia.chegada_confirmada_em = datetime.utcnow()
    db.session.commit()
    return ocorrencia


def finalizar_ocorrencia(ocorrencia_id, desfecho, usuario_atual):
    """HU-020/HOSP-03. RN implícita: só finaliza depois de confirmar
    chegada (marcar_chegada). RN-023: gera o relatório logo em seguida,
    mas uma falha na geração do relatório NUNCA desfaz a finalização —
    ela já está commitada antes de tentarmos montar o relatório."""
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_operacao(ocorrencia, usuario_atual, StatusOcorrenciaEnum.em_transporte)

    if ocorrencia.chegada_confirmada_em is None:
        raise OcorrenciaError(MENSAGEM_FINALIZAR_SEM_CHEGADA)

    desfecho = (desfecho or "").strip()
    if not desfecho:
        raise OcorrenciaError("O campo desfecho é obrigatório.", campo="desfecho")

    ocorrencia.status = StatusOcorrenciaEnum.finalizada
    ocorrencia.finalizado_em = datetime.utcnow()
    ocorrencia.desfecho = desfecho

    # RN-022: encerra o chat na MESMA transação — import local pra não
    # criar import circular (chat_service já importa este módulo).
    from app.services import chat_service

    chat_service.encerrar_chat(ocorrencia)

    db.session.commit()
    return ocorrencia


def gerar_relatorio(ocorrencia_id, usuario_atual):
    """RN-023: calculado sob demanda a partir dos dados já existentes (não
    persistido em tabela própria — decisão registrada na conversa: evita
    duplicar dado e torna "gerar de novo se falhar" trivial). Registra a
    geração na Auditoria; a chamada não falha se o registro de auditoria
    falhar por algum motivo improvável — a finalização já está garantida
    de qualquer forma."""
    ocorrencia = obter_ocorrencia(ocorrencia_id)
    verificar_acesso_leitura_ocorrencia(ocorrencia, usuario_atual)

    if ocorrencia.status != StatusOcorrenciaEnum.finalizada:
        raise OcorrenciaError("Esta ocorrência ainda não foi finalizada.")

    tempo_atendimento_min = None
    if ocorrencia.finalizado_em:
        delta = ocorrencia.finalizado_em - ocorrencia.criado_em
        tempo_atendimento_min = round(delta.total_seconds() / 60, 1)

    relatorio = {
        "ocorrencia_id": ocorrencia.id,
        "socorrista_nome": ocorrencia.socorrista.usuario.nome,
        "socorrista_matricula": ocorrencia.socorrista.matricula,
        "hospital_nome": ocorrencia.hospital.nome if ocorrencia.hospital else None,
        "pacientes": [
            {
                "nome": p.nome,
                "cpf": p.cpf,
                "idade": p.idade,
                "diagnostico": p.diagnostico,
                "fotos": len(p.anexos),
            }
            for p in listar_pacientes_ordenados(ocorrencia)
        ],
        "tempo_atendimento_min": tempo_atendimento_min,
        "desfecho": ocorrencia.desfecho,
        "finalizado_em": ocorrencia.finalizado_em,
    }

    try:
        db.session.add(
            Auditoria(
                tipo_operacao=TipoOperacaoEnum.relatorio_gerado,
                entidade_tipo=EntidadeAuditoriaEnum.ocorrencia,
                entidade_id=ocorrencia.id,
                admin_id=usuario_atual.id,
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    return relatorio
