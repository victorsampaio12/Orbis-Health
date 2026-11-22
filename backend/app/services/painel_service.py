"""Dados da "Lista de emergência" do hospital: cards + mapa com todas as
emergências a caminho. Só monta estruturas simples (dicts) — o template e o
JS do painel não precisam conhecer os models."""

import json

from sqlalchemy import func

from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum
from app.services import ocorrencia_service, rota_service, trajeto_service

ROTULO_ATENDIMENTO = "Em atendimento"
ROTULO_PENDENTE = "Pendente"
ROTULO_FINALIZADA = "Finalizada"


def _iso_utc(momento):
    return momento.isoformat() + "Z" if momento else None


def status_rotulo(ocorrencia):
    if ocorrencia.status == StatusOcorrenciaEnum.finalizada:
        return "finalizada", ROTULO_FINALIZADA
    if ocorrencia.trajeto_iniciado_em is not None:
        return "atendimento", ROTULO_ATENDIMENTO
    return "pendente", ROTULO_PENDENTE


# O painel é a operação do momento: todas as ativas + as últimas finalizadas.
# O histórico completo fica na tela "Histórico de emergências" (paginada).
# Sem esse limite, um hospital com 10 mil atendimentos levava 21 s e 42 MB
# para abrir o painel (Plano de Testes, 7.2.8 Volume).
FINALIZADAS_NO_PAINEL = 30


def montar_emergencias(hospital):
    """Ocorrências deste hospital (RN-007): ativas primeiro, depois as
    FINALIZADAS_NO_PAINEL finalizadas mais recentes."""
    da_casa = Ocorrencia.query.filter(Ocorrencia.hospital_id == hospital.id)
    ativas = (
        da_casa.filter(Ocorrencia.status != StatusOcorrenciaEnum.finalizada)
        .order_by(Ocorrencia.criado_em.desc())
        .all()
    )
    finalizadas = (
        da_casa.filter(Ocorrencia.status == StatusOcorrenciaEnum.finalizada)
        .order_by(func.coalesce(Ocorrencia.finalizado_em, Ocorrencia.criado_em).desc())
        .limit(FINALIZADAS_NO_PAINEL)
        .all()
    )

    emergencias = []
    for ocorrencia in ativas + finalizadas:
        ativa = ocorrencia.status == StatusOcorrenciaEnum.em_transporte
        if ativa:
            # Retoma trajetos parados por um reinício do servidor — o hospital
            # pode abrir só esta lista, sem nunca entrar na página da ocorrência.
            trajeto_service.garantir_em_execucao(ocorrencia)
        status, rotulo = status_rotulo(ocorrencia)
        socorrista = ocorrencia.socorrista
        pacientes = ocorrencia_service.listar_pacientes_ordenados(ocorrencia)

        emergencias.append(
            {
                "id": ocorrencia.id,
                "veiculo": ocorrencia.veiculo.value,
                "local": ocorrencia.local,
                "status": status,
                "status_rotulo": rotulo,
                "ativa": ativa,
                "progresso": 1.0 if not ativa else rota_service.progresso_na_rota(ocorrencia),
                "posicao": (
                    [ocorrencia.latitude_atual, ocorrencia.longitude_atual]
                    if ativa and ocorrencia.latitude_atual is not None
                    else None
                ),
                "rota_geometria": (
                    json.loads(ocorrencia.rota_geometria)
                    if ativa and ocorrencia.rota_geometria
                    else None
                ),
                "tempo_estimado_min": ocorrencia.tempo_estimado_min if ativa else None,
                "criado_em": _iso_utc(ocorrencia.criado_em),
                "saida_em": _iso_utc(ocorrencia.trajeto_iniciado_em),
                "chegada_em": _iso_utc(ocorrencia.chegada_confirmada_em),
                "finalizado_em": _iso_utc(ocorrencia.finalizado_em),
                "trajeto_estado": trajeto_service.estado(ocorrencia),
                "socorrista": {
                    "nome": socorrista.usuario.nome,
                    "email": socorrista.usuario.email,
                    "telefone": socorrista.telefone,
                },
                "total_pacientes": len(pacientes),
                "total_fotos": sum(len(p.anexos) for p in pacientes),
                "maior_prioridade": pacientes[0].prioridade.value if pacientes else None,
            }
        )
    return emergencias
