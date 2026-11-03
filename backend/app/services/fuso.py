"""O banco guarda os horários em UTC (datetime.utcnow()). Na tela, quem
converte é o navegador ([data-utc] em preferencias.js); estes helpers são
para o que o servidor precisa no fuso da operação: "que dia é hoje", os
filtros por data e o CSV exportado."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def _fuso():
    return ZoneInfo(current_app.config["FUSO_HORARIO"])


def hoje_local():
    return datetime.now(_fuso()).date()


def inicio_do_dia_em_utc(dia):
    """00:00 do `dia` no fuso local, convertido para UTC (naive, como no banco)."""
    local = datetime.combine(dia, time.min, tzinfo=_fuso())
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def fim_do_dia_em_utc(dia):
    return inicio_do_dia_em_utc(dia + timedelta(days=1))


def utc_para_local(momento):
    if momento is None:
        return None
    return momento.replace(tzinfo=timezone.utc).astimezone(_fuso()).replace(tzinfo=None)
