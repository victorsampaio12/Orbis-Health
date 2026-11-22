""""Histórico de emergências" do hospital: lista com filtro/paginação de
TODAS as ocorrências (não só finalizadas, ao contrário do Inbox) direcionadas
a este hospital, pra ele acompanhar o que já foi atendido e o que ainda está
em andamento."""

import csv
import io

from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum, VeiculoEnum
from app.models.socorrista import Socorrista
from app.models.usuario import Usuario
from app.services import fuso, painel_service

POR_PAGINA_PADRAO = 8

VEICULO_ROTULO = {"ambulancia": "Ambulância", "helicoptero": "Helicóptero"}


def _query_base(hospital, filtros):
    query = (
        Ocorrencia.query.join(Socorrista, Ocorrencia.socorrista_id == Socorrista.id)
        .join(Usuario, Socorrista.usuario_id == Usuario.id)
        .filter(Ocorrencia.hospital_id == hospital.id)
    )

    busca = (filtros.get("busca") or "").strip()
    if busca:
        codigo = busca.upper().removeprefix("EMG-").lstrip("0")
        condicoes = [Usuario.nome.ilike(f"%{busca}%"), Ocorrencia.local.ilike(f"%{busca}%")]
        if codigo.isascii() and codigo.isdigit() and len(codigo) < 10:
            condicoes.append(Ocorrencia.id == int(codigo))
        from sqlalchemy import or_

        query = query.filter(or_(*condicoes))

    status = filtros.get("status")
    if status == "finalizada":
        query = query.filter(Ocorrencia.status == StatusOcorrenciaEnum.finalizada)
    elif status == "atendimento":
        query = query.filter(
            Ocorrencia.status == StatusOcorrenciaEnum.em_transporte,
            Ocorrencia.trajeto_iniciado_em.isnot(None),
        )
    elif status == "pendente":
        from sqlalchemy import and_, or_

        query = query.filter(
            or_(
                Ocorrencia.status == StatusOcorrenciaEnum.aberta,
                and_(
                    Ocorrencia.status == StatusOcorrenciaEnum.em_transporte,
                    Ocorrencia.trajeto_iniciado_em.is_(None),
                ),
            )
        )

    veiculo = filtros.get("veiculo")
    if veiculo in ("ambulancia", "helicoptero"):
        query = query.filter(Ocorrencia.veiculo == VeiculoEnum(veiculo))

    data_inicio = filtros.get("data_inicio")
    if data_inicio:
        query = query.filter(Ocorrencia.criado_em >= fuso.inicio_do_dia_em_utc(data_inicio))

    data_fim = filtros.get("data_fim")
    if data_fim:
        query = query.filter(Ocorrencia.criado_em < fuso.fim_do_dia_em_utc(data_fim))

    return query


def _linha(ocorrencia):
    status, status_rotulo = painel_service.status_rotulo(ocorrencia)
    return {
        "id": ocorrencia.id,
        "status": status,
        "status_rotulo": status_rotulo,
        "veiculo": ocorrencia.veiculo.value,
        "veiculo_rotulo": VEICULO_ROTULO[ocorrencia.veiculo.value],
        "socorrista_nome": ocorrencia.socorrista.usuario.nome,
        "local": ocorrencia.local,
        "hospital_nome": ocorrencia.hospital.nome if ocorrencia.hospital else "—",
        "criado_em": ocorrencia.criado_em,
        "finalizado_em": ocorrencia.finalizado_em,
        "pode_baixar_relatorio": ocorrencia.status == StatusOcorrenciaEnum.finalizada,
    }


def listar(hospital, filtros, pagina=1, por_pagina=POR_PAGINA_PADRAO):
    query = _query_base(hospital, filtros).order_by(Ocorrencia.criado_em.desc())
    total = query.count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(max(1, pagina), total_paginas)

    ocorrencias = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return {
        "itens": [_linha(o) for o in ocorrencias],
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }


def paginas_visiveis(pagina, total_paginas):
    """Números de página a mostrar na paginação (None = reticências), pra
    não listar 50 botões quando o histórico crescer muito."""
    if total_paginas <= 7:
        return list(range(1, total_paginas + 1))

    paginas = {1, total_paginas, pagina, pagina - 1, pagina + 1}
    paginas = sorted(p for p in paginas if 1 <= p <= total_paginas)

    resultado = []
    anterior = None
    for p in paginas:
        if anterior is not None and p - anterior > 1:
            resultado.append(None)
        resultado.append(p)
        anterior = p
    return resultado


def _celula_segura(valor):
    """Texto digitado por usuários começando com = + - @ seria executado como
    fórmula pelo Excel ao abrir o CSV; o apóstrofo faz virar texto puro."""
    valor = "" if valor is None else str(valor)
    return "'" + valor if valor[:1] in ("=", "+", "-", "@", "\t", "\r") else valor


def exportar_csv(hospital, filtros):
    """Mesmos filtros da listagem, mas sem paginação — exporta tudo que bate."""
    ocorrencias = _query_base(hospital, filtros).order_by(Ocorrencia.criado_em.desc()).all()

    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    escritor.writerow(
        ["ID", "Status", "Tipo", "Socorrista", "Local", "Hospital destino", "Início", "Fim"]
    )
    for ocorrencia in ocorrencias:
        linha = _linha(ocorrencia)
        escritor.writerow(
            [
                f"EMG-{linha['id']:04d}",
                linha["status_rotulo"],
                linha["veiculo_rotulo"],
                _celula_segura(linha["socorrista_nome"]),
                _celula_segura(linha["local"]),
                _celula_segura(linha["hospital_nome"]),
                fuso.utc_para_local(linha["criado_em"]).strftime("%d/%m/%Y %H:%M"),
                fuso.utc_para_local(linha["finalizado_em"]).strftime("%d/%m/%Y %H:%M")
                if linha["finalizado_em"] else "",
            ]
        )
    return buffer.getvalue()
