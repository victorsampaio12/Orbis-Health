"""
API JSON do app mobile do socorrista (mobile/, React Native + Expo).

Jornada completa pela API, como o app faz: login com token, ocorrência,
prontuário com foto, escolha de hospital (o hospital na web recebe a
emergência pelo WebSocket), rota, trajeto em tempo real com o socket
autenticado por token, chat, chegada, finalização e histórico.
"""
import io
import time
from datetime import datetime, timedelta

import pytest
import requests
import socketio as sio_client
from PIL import Image

from apoio import SENHA_PADRAO
from conftest import BASE_URL

API = f"{BASE_URL}/api/v1"
pytestmark = pytest.mark.usefixtures("servidor")


def _foto():
    buf = io.BytesIO()
    Image.new("RGB", (80, 60), (30, 120, 200)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def conta(db_app):
    from app import db
    from app.models.usuario import Usuario
    from app.services import cadastro_service

    admin0 = Usuario.query.filter_by(email="admin0@t.com").first()
    cadastro_service.criar_socorrista({
        "nome": "Socorrista do App", "matricula": "APP-0001", "telefone": "61988880001",
        "email": "app_soc@t.com", "senha": SENHA_PADRAO}, admin0)
    hospital = cadastro_service.criar_hospital({
        "nome": "Hospital do App", "endereco": "SMHS Quadra 101, Brasília - DF",
        "latitude": "-15.80033", "longitude": "-47.88842", "capacidade_maxima": "20",
        "tem_garagem": "on", "tem_heliponto": "", "responsavel_nome": "Resp App",
        "email": "app_hosp@t.com", "senha": SENHA_PADRAO}, admin0)
    db.session.commit()
    r = requests.post(f"{API}/login", json={"email": "app_soc@t.com", "senha": SENHA_PADRAO})
    assert r.status_code == 200
    return {"token": r.json()["token"], "hospital_id": hospital.id}


def _h(conta):
    return {"Authorization": f"Bearer {conta['token']}"}


def _recarregar_ocorrencia(oid):
    from app import db
    from app.models.ocorrencia import Ocorrencia
    db.session.expire_all()
    return db.session.get(Ocorrencia, oid)


# ------------------------------------------------------------- login

def test_login_recusa_senha_errada_e_perfis_que_nao_sao_socorrista(conta):
    r = requests.post(f"{API}/login", json={"email": "app_soc@t.com", "senha": "errada"})
    assert r.status_code == 401 and r.json()["erro"] == "E-mail ou senha incorretos!"
    r = requests.post(f"{API}/login", json={"email": "app_hosp@t.com", "senha": SENHA_PADRAO})
    assert r.status_code == 403 and "socorristas" in r.json()["erro"]


def test_sem_token_ou_com_token_falso_e_recusado(conta):
    assert requests.get(f"{API}/eu").status_code == 401
    r = requests.get(f"{API}/eu", headers={"Authorization": "Bearer token-inventado"})
    assert r.status_code == 401


def test_eu_mostra_o_socorrista(conta):
    r = requests.get(f"{API}/eu", headers=_h(conta)).json()
    assert r["usuario"]["matricula"] == "APP-0001" and r["ocorrencia_ativa"] is None


# --------------------------------------------------- jornada completa

class TestJornadaPeloApp:
    estado = {}

    def test_abre_ocorrencia_com_gps(self, conta):
        r = requests.post(f"{API}/ocorrencias", headers=_h(conta), json={
            "local": "Rodoviária do Plano Piloto", "veiculo": "ambulancia",
            "latitude": -15.7939, "longitude": -47.8828})
        assert r.status_code == 201
        dados = r.json()
        assert dados["status"] == "aberta" and dados["posicao"]["latitude"] == pytest.approx(-15.7939)
        self.estado["oid"] = dados["id"]
        # uma ativa por vez
        r = requests.post(f"{API}/ocorrencias", headers=_h(conta), json={"local": "x", "veiculo": "ambulancia"})
        assert r.status_code == 409

    @pytest.mark.regra("RN-010")
    def test_prontuario_com_foto_e_prioridade_do_servidor(self, conta):
        oid = self.estado["oid"]
        r = requests.post(f"{API}/ocorrencias/{oid}/pacientes", headers=_h(conta),
                          data={"nome": "Paciente do App", "motivo_chamado": "Dispneia", "saturacao_o2": "86"},
                          files=[("anexos", ("ecg.jpg", _foto(), "image/jpeg"))])
        assert r.status_code == 201
        p = r.json()
        assert p["prioridade"] == "critica" and len(p["anexos"]) == 1
        self.estado["pid"], self.estado["anexo"] = p["id"], p["anexos"][0]

        foto = requests.get(BASE_URL + self.estado["anexo"]["miniatura"], headers=_h(conta))
        assert foto.status_code == 200 and foto.headers["Content-Type"] == "image/jpeg"
        assert requests.get(BASE_URL + self.estado["anexo"]["url"]).status_code == 401

        # inválido continua inválido pela API (mesma validação da web)
        r = requests.post(f"{API}/ocorrencias/{oid}/pacientes", headers=_h(conta),
                          data={"nome": "X", "motivo_chamado": "Y", "glasgow": "40"})
        assert r.status_code == 400 and "Glasgow" in r.json()["erro"]

    def test_edita_prontuario_e_remove_foto(self, conta):
        oid, pid = self.estado["oid"], self.estado["pid"]
        r = requests.post(f"{API}/ocorrencias/{oid}/pacientes/{pid}", headers=_h(conta),
                          data={"nome": "Paciente do App", "motivo_chamado": "Dispneia", "saturacao_o2": "95",
                                "remover_anexo": str(self.estado["anexo"]["id"])})
        assert r.status_code == 200
        assert r.json()["prioridade"] == "media" and r.json()["anexos"] == []
        assert requests.get(f"{API}/ocorrencias/{oid}/pacientes/{pid}", headers=_h(conta)).json()["nome"] == \
            "Paciente do App"

    def test_regioes_da_lesao_no_boneco_3d(self, conta):
        """Regiões marcadas no corpo 3D: aceita o campo repetido (web) ou a
        lista com vírgula (app), ignora códigos desconhecidos e guarda na
        ordem do corpo (de cima para baixo)."""
        oid, pid = self.estado["oid"], self.estado["pid"]
        url = f"{API}/ocorrencias/{oid}/pacientes/{pid}"
        base = {"nome": "Paciente do App", "motivo_chamado": "Dispneia"}

        r = requests.post(url, headers=_h(conta), data={**base, "regioes_lesao": ["perna_direita", "cabeca", "asa"]})
        assert r.status_code == 200 and r.json()["regioes_lesao"] == ["cabeca", "perna_direita"]

        r = requests.post(url, headers=_h(conta), data={**base, "regioes_lesao": "torax,braco_esquerdo"})
        assert r.json()["regioes_lesao"] == ["torax", "braco_esquerdo"]

        r = requests.post(url, headers=_h(conta), data=base)  # nada marcado limpa
        assert r.json()["regioes_lesao"] == []

    @pytest.mark.regra("RN-003", "RN-006")
    @pytest.mark.eventos_ws("nova_emergencia", "emergencia_cancelada")
    def test_escolhe_hospital_e_o_hospital_na_web_e_avisado(self, conta):
        oid, hid = self.estado["oid"], conta["hospital_id"]
        lista = requests.get(f"{API}/ocorrencias/{oid}/hospitais", headers=_h(conta)).json()["hospitais"]
        assert any(h["id"] == hid for h in lista)
        assert all("distancia_km" in h and h["status"] in ("disponivel", "critico", "lotado") for h in lista)

        # o hospital, logado na web (cookie), escuta a própria sala
        web = requests.Session()
        web.post(f"{BASE_URL}/login", data={"email": "app_hosp@t.com", "senha": SENHA_PADRAO})
        avisos = []
        hosp = sio_client.Client(reconnection=False)
        hosp.on("nova_emergencia", lambda d: avisos.append(("nova", d)))
        hosp.on("emergencia_cancelada", lambda d: avisos.append(("cancelada", d)))
        hosp.connect(BASE_URL, headers={"Cookie": f"session={web.cookies['session']}"})
        hosp.emit("entrar_sala_hospital", {"hospital_id": hid})
        hosp.sleep(0.5)

        r = requests.post(f"{API}/ocorrencias/{oid}/hospital", headers=_h(conta), json={"hospital_id": hid})
        assert r.status_code == 200 and r.json()["status"] == "em_transporte"
        assert r.json()["pode_trocar_hospital"] is True
        r = requests.post(f"{API}/ocorrencias/{oid}/trocar-hospital", headers=_h(conta))
        assert r.status_code == 200 and r.json()["status"] == "aberta"
        r = requests.post(f"{API}/ocorrencias/{oid}/hospital", headers=_h(conta), json={"hospital_id": hid})
        assert r.status_code == 200
        hosp.sleep(1.0)
        hosp.disconnect()
        assert [t for t, _ in avisos] == ["nova", "cancelada", "nova"]

    @pytest.mark.eventos_ws("connect", "localizacao_atualizada")
    def test_trajeto_em_tempo_real_com_socket_autenticado_por_token(self, conta):
        oid = self.estado["oid"]
        r = requests.post(f"{API}/ocorrencias/{oid}/rota", headers=_h(conta))
        assert r.status_code == 200 and r.json()["rota"], r.text

        posicoes = []
        app = sio_client.Client(reconnection=False)
        app.on("localizacao_atualizada", lambda d: posicoes.append(d))
        app.connect(BASE_URL, auth={"token": conta["token"]})
        app.emit("entrar_sala_ocorrencia", {"ocorrencia_id": oid})
        app.sleep(0.5)
        r = requests.post(f"{API}/ocorrencias/{oid}/iniciar-trajeto", headers=_h(conta))
        assert r.status_code == 200 and r.json()["trajeto_estado"] == "em_andamento"
        limite = time.monotonic() + 8
        while not posicoes and time.monotonic() < limite:
            app.sleep(0.3)
        app.disconnect()
        assert posicoes and posicoes[0]["ocorrencia_id"] == oid

        # socket com token inválido não entra na sala de ninguém
        intruso = []
        falso = sio_client.Client(reconnection=False)
        falso.on("localizacao_atualizada", lambda d: intruso.append(d))
        falso.connect(BASE_URL, auth={"token": "token-falso"})
        falso.emit("entrar_sala_ocorrencia", {"ocorrencia_id": oid})
        falso.sleep(2.5)
        falso.disconnect()
        assert intruso == []

    @pytest.mark.regra("RN-016")
    def test_chat_pela_api(self, conta):
        oid = self.estado["oid"]
        r = requests.post(f"{API}/ocorrencias/{oid}/mensagens", headers=_h(conta),
                          json={"conteudo": "Chegando em 10 minutos, paciente estável."})
        assert r.status_code == 201
        dados = requests.get(f"{API}/ocorrencias/{oid}/mensagens", headers=_h(conta)).json()
        assert dados["mensagens"][-1]["conteudo"].startswith("Chegando") and dados["chat_encerrado"] is False

    @pytest.mark.regra("RN-022", "RN-023")
    def test_chegada_finalizacao_e_historico(self, conta):
        from app import db

        oid = self.estado["oid"]
        r = requests.post(f"{API}/ocorrencias/{oid}/chegada", headers=_h(conta))
        assert r.status_code == 400  # ainda longe do hospital (HU-021)

        # fim do trajeto simulado: viatura na porta do hospital
        o = _recarregar_ocorrencia(oid)
        o.trajeto_iniciado_em = datetime.utcnow() - timedelta(hours=1)
        o.latitude_atual, o.longitude_atual = o.destino_latitude, o.destino_longitude
        db.session.commit()

        assert requests.post(f"{API}/ocorrencias/{oid}/chegada", headers=_h(conta)).status_code == 200
        r = requests.post(f"{API}/ocorrencias/{oid}/finalizar", headers=_h(conta),
                          json={"desfecho": "Paciente internado na sala vermelha."})
        assert r.status_code == 200
        assert r.json()["ocorrencia"]["status"] == "finalizada" and r.json()["ocorrencia"]["chat_encerrado"]
        assert r.json()["relatorio"]["hospital_nome"] == "Hospital do App"

        hist = requests.get(f"{API}/historico", headers=_h(conta)).json()
        assert hist[0]["id"] == oid and hist[0]["pacientes"] == 1
        detalhe = requests.get(f"{API}/ocorrencias/{oid}", headers=_h(conta)).json()
        assert detalhe["status"] == "finalizada"
        # depois de finalizada, posição não muda mais (D11)
        r = requests.post(f"{API}/ocorrencias/{oid}/localizacao", headers=_h(conta), json={"lat": -15.7, "lng": -47.9})
        assert r.status_code == 400


@pytest.mark.regra("RN-007")
def test_socorrista_nao_ve_ocorrencia_de_outro_pela_api(conta, db_app):
    from app import db
    from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum, VeiculoEnum
    from app.models.socorrista import Socorrista

    outro = Socorrista.query.filter(Socorrista.matricula != "APP-0001").first()
    if outro is None:
        from app.models.usuario import Usuario
        from app.services import cadastro_service
        outro = cadastro_service.criar_socorrista({
            "nome": "Outro Socorrista", "matricula": "APP-0002", "telefone": "",
            "email": "app_outro@t.com", "senha": SENHA_PADRAO},
            Usuario.query.filter_by(email="admin0@t.com").first())
    o = Ocorrencia(socorrista_id=outro.id, veiculo=VeiculoEnum.ambulancia,
                   status=StatusOcorrenciaEnum.aberta, local="Ocorrência alheia")
    db.session.add(o)
    db.session.commit()
    assert requests.get(f"{API}/ocorrencias/{o.id}", headers=_h(conta)).status_code == 403
    assert requests.get(f"{API}/ocorrencias/999999", headers=_h(conta)).status_code == 404
