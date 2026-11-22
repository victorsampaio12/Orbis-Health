"""
Modo demonstração (apresentação do TCC): quem escaneia o QR code entra como
socorrista sem cadastro e faz o fluxo completo pelo celular — cada visitante
com a própria conta, trajeto curto, hospital respondendo sozinho no chat,
sem envio de fotos e com tudo apagado depois de 24 h.
"""
import io
import re

import pytest
from PIL import Image


CELULAR = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
    "geolocation": {"latitude": -15.8040, "longitude": -47.8884},
    "permissions": ["geolocation"],
    "locale": "pt-BR",
    "timezone_id": "America/Sao_Paulo",
}


def _ocorrencia(ocorrencia_id):
    from app import db
    from app.models.ocorrencia import Ocorrencia

    db.session.expire_all()
    return db.session.get(Ocorrencia, ocorrencia_id)


def _entrar_como_visitante(browser, servidor):
    contexto = browser.new_context(**CELULAR)
    page = contexto.new_page()
    page.goto(f"{servidor}/demo/")
    page.click('button:has-text("Começar como socorrista")')
    page.wait_for_load_state("networkidle")
    return contexto, page


@pytest.fixture(scope="class")
def visitante(browser, servidor):
    contexto, page = _entrar_como_visitante(browser, servidor)
    yield page
    contexto.close()


_ESTADO = {}   # compartilhado entre os passos da jornada (com e sem navegador)


@pytest.fixture
def estado():
    return _ESTADO


class TestModoDemonstracao:
    def test_qr_code_leva_a_formulario_sem_senha(self, visitante, servidor, estado, db_app):
        from app.models.usuario import Usuario
        from app.services import demo_service

        assert visitante.url.endswith("/ocorrencias/novo")
        visitante.wait_for_function("document.getElementById('local').value.length > 0", timeout=15000)
        usuarios = Usuario.query.filter(Usuario.email.like(f"%{demo_service.DOMINIO_VISITANTE}")).all()
        assert len(usuarios) == 1 and usuarios[0].socorrista is not None
        assert usuarios[0].nome.startswith("Visitante ")

    def test_abre_a_ocorrencia(self, visitante, estado, db_app):
        visitante.select_option("#veiculo", "ambulancia")
        visitante.click('button[type="submit"]')
        visitante.wait_for_load_state("networkidle")
        m = re.search(r"/ocorrencias/(\d+)$", visitante.url)
        assert m is not None, visitante.url
        estado["id"] = int(m.group(1))
        ocorrencia = _ocorrencia(estado["id"])
        assert ocorrencia.status.value == "aberta" and ocorrencia.latitude_atual is not None

    def test_visitante_nao_envia_fotos(self, visitante, servidor, estado, db_app):
        visitante.goto(f"{servidor}/ocorrencias/{estado['id']}/pacientes/novo")
        assert visitante.locator("#anexos").count() == 0      # campo nem aparece

        # e o servidor ignora uma foto enviada por fora do formulário
        foto = io.BytesIO()
        Image.new("RGB", (40, 40), "red").save(foto, "JPEG")
        resp = visitante.request.post(
            f"{servidor}/ocorrencias/{estado['id']}/pacientes/novo",
            multipart={
                "nome": "Paciente da demonstração",
                "motivo_chamado": "Dor torácica (simulação)",
                "anexos": {"name": "cena.jpg", "mimeType": "image/jpeg", "buffer": foto.getvalue()},
            },
        )
        assert resp.ok
        pacientes = _ocorrencia(estado["id"]).pacientes
        assert len(pacientes) == 1 and len(pacientes[0].anexos) == 0

    def test_escolhe_hospital_e_trajeto_dura_poucos_minutos(self, visitante, servidor, estado, db_app):
        visitante.goto(f"{servidor}/ocorrencias/{estado['id']}/hospitais")
        visitante.locator(".hospital-card", has_text="Hospital de Base").locator(
            'button:has-text("Selecionar")'
        ).click()
        visitante.wait_for_load_state("networkidle")
        visitante.click("#btn-gerar-rota")
        visitante.wait_for_load_state("networkidle")
        resp = visitante.request.post(f"{servidor}/ocorrencias/{estado['id']}/iniciar-trajeto")
        assert resp.ok

        ocorrencia = _ocorrencia(estado["id"])
        assert ocorrencia.trajeto_iniciado_em is not None
        assert 60 <= ocorrencia.trajeto_duracao_s <= 150

    def test_hospital_responde_sozinho_no_chat(self, visitante, servidor, estado):
        visitante.goto(f"{servidor}/ocorrencias/{estado['id']}")
        visitante.fill("#chat-input", "Paciente consciente, chegamos em breve.")
        visitante.click('#chat-form button[type="submit"]')
        visitante.locator("#chat-mensagens", has_text="Recebemos o seu chamado").wait_for(timeout=15000)
        assert "Hospital de Base" in visitante.inner_text("#chat-mensagens")

    def test_cada_visitante_tem_a_propria_conta(self, browser, servidor, estado, db_app):
        from app.models.usuario import Usuario
        from app.services import demo_service

        contexto, outro = _entrar_como_visitante(browser, servidor)
        try:
            assert outro.url.endswith("/ocorrencias/novo")      # não herda a ocorrência do primeiro
            resp = outro.request.get(f"{servidor}/ocorrencias/{estado['id']}")
            assert resp.status in (403, 404) or "/ocorrencias/novo" in resp.url
        finally:
            contexto.close()
        assert Usuario.query.filter(Usuario.email.like(f"%{demo_service.DOMINIO_VISITANTE}")).count() == 2

    def test_qr_code_para_projetar(self, browser, servidor):
        from apoio import login

        contexto = browser.new_context()
        page = contexto.new_page()
        try:
            login(page, servidor, "admin0@t.com")
            page.goto(f"{servidor}/demo/qrcode")
            assert page.locator(".demo-qr-codigo svg").count() == 1
            assert "/demo/" in page.inner_text(".demo-qr-endereco")
        finally:
            contexto.close()

    def test_contas_de_visitante_somem_depois_de_24h(self, estado, db_app):
        from app.models.ocorrencia import Ocorrencia
        from app.models.usuario import Usuario
        from app.services import demo_service

        assert demo_service.limpar_expirados(horas=0) == 2
        assert Usuario.query.filter(Usuario.email.like(f"%{demo_service.DOMINIO_VISITANTE}")).count() == 0
        assert Ocorrencia.query.filter_by(id=estado["id"]).count() == 0


def test_sem_modo_demonstracao_a_entrada_nao_existe(db_app, monkeypatch):
    from app import create_app
    from app.config.config import Config

    monkeypatch.setattr(Config, "MODO_DEMONSTRACAO", False)
    cliente = create_app().test_client()
    assert cliente.get("/demo/").status_code == 404
    assert cliente.post("/demo/entrar").status_code == 404


def test_visitantes_nao_aparecem_no_cadastro_nem_nos_kpis(db_app):
    from app.services import cadastro_service, dashboard_service, demo_service

    antes = dashboard_service.montar_kpis()["socorristas"]
    visitante = demo_service.criar_visitante("203.0.113.9")
    try:
        assert visitante.socorrista not in cadastro_service.listar_socorristas()
        assert dashboard_service.montar_kpis()["socorristas"] == antes
    finally:
        demo_service.limpar_expirados(horas=0)
