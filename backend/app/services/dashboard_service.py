"""KPIs do dashboard do admin — visão geral do sistema inteiro (não de um
hospital específico, como o painel_service). Só leitura: nenhuma função
aqui muda dado nenhum."""

from datetime import datetime

from app import db
from app.models.auditoria import Auditoria
from app.models.hospital import Hospital
from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum, VeiculoEnum
from app.models.socorrista import Socorrista
from app.models.usuario import PapelEnum, Usuario
from app.services import fuso, ocorrencia_service

ATIVAS = (StatusOcorrenciaEnum.aberta, StatusOcorrenciaEnum.em_transporte)

ROTULO_OPERACAO = {
    "criacao": "criou",
    "edicao": "editou",
    "desativacao": "desativou",
    "exclusao": "excluiu",
    "relatorio_gerado": "gerou relatório de",
}
ROTULO_ENTIDADE = {
    "hospital": "hospital",
    "socorrista": "socorrista",
    "admin": "administrador",
    "ocorrencia": "ocorrência",
}


def _inicio_do_dia():
    return fuso.inicio_do_dia_em_utc(fuso.hoje_local())


def _tempo_medio_atendimento_min(limite=100):
    """Média de (finalizado_em - criado_em) das últimas `limite` ocorrências
    finalizadas — amostra recente, não o histórico inteiro, pra refletir o
    desempenho atual e não ficar pesado com o tempo."""
    finalizadas = (
        Ocorrencia.query.filter(
            Ocorrencia.status == StatusOcorrenciaEnum.finalizada,
            Ocorrencia.finalizado_em.isnot(None),
        )
        .order_by(Ocorrencia.finalizado_em.desc())
        .limit(limite)
        .all()
    )
    if not finalizadas:
        return None
    duracoes_min = [
        (o.finalizado_em - o.criado_em).total_seconds() / 60 for o in finalizadas
    ]
    return round(sum(duracoes_min) / len(duracoes_min), 1)


def _hospitais_com_status():
    return [
        (hospital, ocorrencia_service.status_capacidade(hospital)[0])
        for hospital in Hospital.query.filter_by(ativo=True).order_by(Hospital.id).all()
    ]


def _capacidade_hospitais(hospitais_status):
    contagem = {"disponivel": 0, "critico": 0, "lotado": 0}
    for _, status in hospitais_status:
        contagem[status] += 1
    return contagem


def _mapa_operacao(hospitais_status):
    """Hospitais ativos e viaturas em atendimento, para o mapa do dashboard."""
    hospitais = [
        {"id": h.id, "nome": h.nome, "lat": h.latitude, "lng": h.longitude, "status": status}
        for h, status in hospitais_status
        if h.latitude is not None and h.longitude is not None
    ]
    viaturas = []
    for o in Ocorrencia.query.filter(Ocorrencia.status.in_(ATIVAS)).order_by(Ocorrencia.id).all():
        lat, lng = o.latitude_atual, o.longitude_atual
        if lat is None or lng is None:
            continue
        viaturas.append({
            "id": o.id,
            "codigo": f"EMG-{o.id:04d}",
            "veiculo": o.veiculo.value,
            "status": o.status.value,
            "lat": lat,
            "lng": lng,
            "destino": (
                [o.destino_latitude, o.destino_longitude] if o.destino_latitude is not None else None
            ),
            "hospital": o.hospital.nome if o.hospital else None,
            "local": o.local,
        })
    return {"hospitais": hospitais, "viaturas": viaturas}


def _nome_da_entidade(tipo, entidade_id):
    """Nome legível do registro afetado (ex.: o nome do hospital), em vez de
    só o id. Se o registro já foi excluído, cai no "#id"."""
    if tipo == "ocorrencia":
        return f"EMG-{entidade_id:04d}"
    if tipo == "hospital":
        registro = db.session.get(Hospital, entidade_id)
        nome = registro.nome if registro else None
    elif tipo == "socorrista":
        registro = db.session.get(Socorrista, entidade_id)
        nome = registro.usuario.nome if registro else None
    else:
        registro = db.session.get(Usuario, entidade_id)
        nome = registro.nome if registro else None
    return nome or f"#{entidade_id}"


def _ultimas_acoes(limite=8):
    auditorias = (
        Auditoria.query.order_by(Auditoria.criado_em.desc()).limit(limite).all()
    )
    acoes = []
    for registro in auditorias:
        tipo = registro.entidade_tipo.value
        acoes.append(
            {
                "admin_nome": registro.admin.nome if registro.admin else "Admin removido",
                "operacao": ROTULO_OPERACAO.get(registro.tipo_operacao.value, registro.tipo_operacao.value),
                "entidade": ROTULO_ENTIDADE.get(tipo, tipo),
                "entidade_id": registro.entidade_id,
                "entidade_nome": _nome_da_entidade(tipo, registro.entidade_id),
                "criado_em": registro.criado_em.isoformat() + "Z",
            }
        )
    return acoes


def montar_kpis():
    hospitais_total = Hospital.query.count()
    hospitais_ativos = Hospital.query.filter_by(ativo=True).count()

    # visitantes do modo demonstração não contam como equipe
    from app.services.demo_service import DOMINIO_VISITANTE

    equipe = Socorrista.query.join(Usuario, Socorrista.usuario_id == Usuario.id).filter(
        ~Usuario.email.like(f"%{DOMINIO_VISITANTE}")
    )
    socorristas_total = equipe.count()
    socorristas_ativos = equipe.filter(Usuario.ativo.is_(True)).count()

    admins_total = Usuario.query.filter_by(papel=PapelEnum.admin).count()

    ocorrencias_abertas = Ocorrencia.query.filter_by(status=StatusOcorrenciaEnum.aberta).count()
    ocorrencias_transporte = Ocorrencia.query.filter_by(
        status=StatusOcorrenciaEnum.em_transporte
    ).count()

    finalizadas_hoje = Ocorrencia.query.filter(
        Ocorrencia.status == StatusOcorrenciaEnum.finalizada,
        Ocorrencia.finalizado_em >= _inicio_do_dia(),
    ).count()

    total_ocorrencias = Ocorrencia.query.count()
    total_finalizadas = Ocorrencia.query.filter_by(
        status=StatusOcorrenciaEnum.finalizada
    ).count()

    ambulancias_ativas = Ocorrencia.query.filter(
        Ocorrencia.veiculo == VeiculoEnum.ambulancia, Ocorrencia.status.in_(ATIVAS)
    ).count()
    helicopteros_ativos = Ocorrencia.query.filter(
        Ocorrencia.veiculo == VeiculoEnum.helicoptero, Ocorrencia.status.in_(ATIVAS)
    ).count()

    hospitais_status = _hospitais_com_status()

    return {
        "atualizado_em": datetime.utcnow().isoformat() + "Z",
        "hospitais": {"total": hospitais_total, "ativos": hospitais_ativos},
        "socorristas": {"total": socorristas_total, "ativos": socorristas_ativos},
        "admins_total": admins_total,
        "ocorrencias_ativas": ocorrencias_abertas + ocorrencias_transporte,
        "ocorrencias_abertas": ocorrencias_abertas,
        "ocorrencias_transporte": ocorrencias_transporte,
        "finalizadas_hoje": finalizadas_hoje,
        "total_ocorrencias": total_ocorrencias,
        "total_finalizadas": total_finalizadas,
        "tempo_medio_atendimento_min": _tempo_medio_atendimento_min(),
        "capacidade_hospitais": _capacidade_hospitais(hospitais_status),
        "mapa": _mapa_operacao(hospitais_status),
        "veiculos_ativos": {"ambulancia": ambulancias_ativas, "helicoptero": helicopteros_ativos},
        "ultimas_acoes": _ultimas_acoes(),
    }
