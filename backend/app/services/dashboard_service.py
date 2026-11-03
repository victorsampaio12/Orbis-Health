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


def _capacidade_hospitais():
    contagem = {"disponivel": 0, "critico": 0, "lotado": 0}
    for hospital in Hospital.query.filter_by(ativo=True).all():
        status, _ = ocorrencia_service.status_capacidade(hospital)
        contagem[status] += 1
    return contagem


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

    socorristas_total = Socorrista.query.count()
    socorristas_ativos = (
        Socorrista.query.join(Usuario, Socorrista.usuario_id == Usuario.id)
        .filter(Usuario.ativo.is_(True))
        .count()
    )

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
        "capacidade_hospitais": _capacidade_hospitais(),
        "veiculos_ativos": {"ambulancia": ambulancias_ativas, "helicoptero": helicopteros_ativos},
        "ultimas_acoes": _ultimas_acoes(),
    }
