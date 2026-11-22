"""Faixas de referência (adulto em repouso) para sinalizar sinais vitais
alterados no pré-prontuário. É só um apoio visual para quem recebe o
paciente — não substitui a avaliação clínica."""

FAIXAS = {
    # tipo: (mínimo normal, máximo normal, texto da referência)
    "fc": (60, 100, "60–100"),
    "fr": (12, 20, "12–20"),
    "spo2": (94, 100, "≥ 94"),
    "temp": (35.5, 37.7, "35,5–37,7"),
    "glasgow": (15, 15, "15"),
}
REF_PA = "< 140/90"


def _numero(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def avaliar(tipo, valor):
    """Retorna (estado, referência). estado: "alto", "baixo", "normal" ou
    None quando não há valor/ não dá para avaliar."""
    if tipo == "pa":
        if valor is None or valor == "":
            return None, REF_PA
        partes = str(valor).replace(" ", "").split("/")
        if len(partes) != 2:
            return None, REF_PA
        sis, dia = _numero(partes[0]), _numero(partes[1])
        if sis is None or dia is None:
            return None, REF_PA
        if sis >= 140 or dia >= 90:
            return "alto", REF_PA
        if sis < 90 or dia < 60:
            return "baixo", REF_PA
        return "normal", REF_PA
    if tipo not in FAIXAS:
        return None, ""
    minimo, maximo, ref = FAIXAS[tipo]
    numero = None if valor is None or valor == "" else _numero(valor)
    if numero is None:
        return None, ref
    if numero < minimo:
        return "baixo", ref
    if numero > maximo:
        return "alto", ref
    return "normal", ref
