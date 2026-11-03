"""Fotos anexadas ao pré-prontuário.

Toda foto recebida é aberta com o Pillow (o que garante que é uma imagem de
verdade, não um arquivo qualquer renomeado), tem a rotação do celular
corrigida e é regravada em JPEG — o que também descarta os metadados EXIF,
inclusive a localização GPS que muitos celulares gravam na foto. Também é
gerada uma miniatura para a galeria.
"""

import io
import os
import uuid

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from app import db
from app.models.anexo import AnexoPaciente

FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP"}
TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024
MAXIMO_POR_PACIENTE = 10
LADO_MAXIMO = 2000
LADO_MINIATURA = 480

MENSAGEM_FORMATO = "Anexo \"{nome}\" não é uma imagem válida (use JPG, PNG ou WEBP)."
MENSAGEM_TAMANHO = "Anexo \"{nome}\" passa de 10 MB."
MENSAGEM_QUANTIDADE = f"Cada paciente pode ter no máximo {MAXIMO_POR_PACIENTE} fotos anexadas."

# Imagens absurdamente grandes (ex.: "bomba de descompressão") são recusadas
# antes de decodificar, em vez de travar o servidor.
Image.MAX_IMAGE_PIXELS = 60_000_000


class AnexoError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def _pasta_raiz():
    return current_app.config["UPLOAD_FOLDER"]


def _caminho_miniatura(arquivo):
    raiz, ext = os.path.splitext(arquivo)
    return f"{raiz}_mini{ext}"


def preparar(arquivos):
    """Valida e processa as fotos EM MEMÓRIA, sem gravar nada — se uma delas
    for inválida, nenhuma é salva e o prontuário também não."""
    preparadas = []
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename:
            continue
        nome = os.path.basename(arquivo.filename)[:255]
        conteudo = arquivo.read()
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            raise AnexoError(MENSAGEM_TAMANHO.format(nome=nome))
        try:
            with Image.open(io.BytesIO(conteudo)) as imagem:
                if imagem.format not in FORMATOS_ACEITOS:
                    raise AnexoError(MENSAGEM_FORMATO.format(nome=nome))
                imagem.load()
                imagem = ImageOps.exif_transpose(imagem).convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise AnexoError(MENSAGEM_FORMATO.format(nome=nome))

        imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
        miniatura = imagem.copy()
        miniatura.thumbnail((LADO_MINIATURA, LADO_MINIATURA))

        principal = io.BytesIO()
        imagem.save(principal, "JPEG", quality=85, optimize=True)
        mini = io.BytesIO()
        miniatura.save(mini, "JPEG", quality=80, optimize=True)
        preparadas.append({
            "nome": nome, "dados": principal.getvalue(), "miniatura": mini.getvalue(),
            "largura": imagem.width, "altura": imagem.height,
        })
    return preparadas


def verificar_quantidade(paciente, novas, removendo=0):
    atuais = len(paciente.anexos) if paciente is not None else 0
    if atuais - removendo + len(novas) > MAXIMO_POR_PACIENTE:
        raise AnexoError(MENSAGEM_QUANTIDADE)


def gravar(paciente, preparadas, usuario):
    """Grava em disco as fotos já validadas por preparar() e registra no
    banco (sem commit — quem chama decide)."""
    pasta = os.path.join(_pasta_raiz(), "anexos", str(paciente.ocorrencia_id))
    os.makedirs(pasta, exist_ok=True)
    for foto in preparadas:
        relativo = os.path.join("anexos", str(paciente.ocorrencia_id), f"{uuid.uuid4().hex}.jpg")
        with open(os.path.join(_pasta_raiz(), relativo), "wb") as f:
            f.write(foto["dados"])
        with open(os.path.join(_pasta_raiz(), _caminho_miniatura(relativo)), "wb") as f:
            f.write(foto["miniatura"])
        db.session.add(AnexoPaciente(
            paciente=paciente, enviado_por_id=usuario.id, nome_original=foto["nome"],
            arquivo=relativo, largura=foto["largura"], altura=foto["altura"],
            tamanho_bytes=len(foto["dados"]),
        ))


def remover(paciente, ids):
    """Remove os anexos indicados (só os deste paciente) do banco e do disco."""
    ids = {int(i) for i in ids if str(i).isdigit()}
    for anexo in [a for a in paciente.anexos if a.id in ids]:
        for relativo in (anexo.arquivo, _caminho_miniatura(anexo.arquivo)):
            try:
                os.remove(os.path.join(_pasta_raiz(), relativo))
            except FileNotFoundError:
                pass
        paciente.anexos.remove(anexo)


def caminho_absoluto(anexo, miniatura=False):
    relativo = _caminho_miniatura(anexo.arquivo) if miniatura else anexo.arquivo
    return os.path.join(_pasta_raiz(), relativo)
