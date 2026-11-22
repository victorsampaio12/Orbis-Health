"""
Regressões da revisão geral do sistema (Plano de Testes PT-ORBIS-001).

Cada teste reproduz um defeito encontrado na revisão de código e falhava
antes da correção. Usam requisições HTTP diretas (como um cliente
malicioso faria, sem passar pela tela) e conferem o banco.
"""
import io
import os
import subprocess
import sys
import threading
from datetime import datetime

import pytest
import requests
import socketio as sio_client
from PIL import Image

from apoio import SENHA_PADRAO
from conftest import BACKEND_DIR, BASE_URL

pytestmark = pytest.mark.usefixtures("servidor")


# ------------------------------------------------------------- apoio

def _sessao(email, senha=SENHA_PADRAO):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/login", data={"email": email, "senha": senha}, allow_redirects=False)
    assert r.status_code in (302, 303), f"login de {email} falhou"
    return s


def _logado(s):
    r = s.get(f"{BASE_URL}/dashboard", allow_redirects=False)
    return r.status_code == 200


def _foto():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def cenario(db_app):
    """Admin, dois socorristas e três hospitais próprios deste módulo."""
    from app import db
    from app.models.usuario import Usuario
    from app.services import cadastro_service

    admin0 = Usuario.query.filter_by(email="admin0@t.com").first()

    def hospital(sufixo, cap, lat, lng):
        return cadastro_service.criar_hospital({
            "nome": f"Hospital Revisão {sufixo}", "endereco": f"Endereço {sufixo}, Brasília - DF",
            "latitude": str(lat), "longitude": str(lng), "capacidade_maxima": str(cap),
            "tem_garagem": "on", "tem_heliponto": "", "responsavel_nome": f"Resp {sufixo}",
            "email": f"rv_hosp_{sufixo.lower()}@t.com", "senha": SENHA_PADRAO,
        }, admin0)

    dados = {
        "admin": admin0,
        "hosp_a": hospital("A", 10, -15.7801, -47.9292),
        "hosp_b": hospital("B", 10, -15.8350, -48.0500),
        "hosp_um_leito": hospital("Um", 1, -15.8700, -47.9900),
        "soc": cadastro_service.criar_socorrista({
            "nome": "Socorrista Revisão", "matricula": "RV-0001", "telefone": "61999990001",
            "email": "rv_soc@t.com", "senha": SENHA_PADRAO}, admin0),
        "soc2": cadastro_service.criar_socorrista({
            "nome": "Socorrista Revisão Dois", "matricula": "RV-0002", "telefone": "61999990002",
            "email": "rv_soc2@t.com", "senha": SENHA_PADRAO}, admin0),
    }
    db.session.commit()
    return dados


def _ocorrencia(socorrista, hospital=None, status="aberta", **extra):
    from app import db
    from app.models.ocorrencia import Ocorrencia, StatusOcorrenciaEnum, TipoRotaEnum, VeiculoEnum
    from app.models.paciente import Paciente, PrioridadeEnum

    o = Ocorrencia(socorrista_id=socorrista.id, veiculo=VeiculoEnum.ambulancia,
                   status=StatusOcorrenciaEnum(status), local="Eixo Monumental, Brasília",
                   latitude_atual=-15.7942, longitude_atual=-47.8822, **extra)
    if hospital is not None:
        o.hospital_id = hospital.id
        o.destino_latitude, o.destino_longitude = hospital.latitude, hospital.longitude
        o.tipo_rota = TipoRotaEnum.terrestre
    db.session.add(o)
    db.session.flush()
    db.session.add(Paciente(ocorrencia_id=o.id, nome="Paciente Revisão", motivo_chamado="Queda",
                            prioridade=PrioridadeEnum.media))
    db.session.commit()
    return o


def _recarregar(obj):
    from app import db
    db.session.expire_all()
    return db.session.get(type(obj), obj.id)


# ------------------------------------------------- 1. contas desativadas

@pytest.mark.regra("RN-020")
def test_admin_desativado_nao_entra_e_perde_a_sessao(cenario):
    from app import db
    from app.services import cadastro_service

    novo = cadastro_service.criar_admin(
        {"nome": "Admin Revisão", "email": "rv_admin@t.com", "senha": SENHA_PADRAO}, cenario["admin"])
    db.session.commit()
    sessao_aberta = _sessao("rv_admin@t.com")
    assert sessao_aberta.get(f"{BASE_URL}/admin/", allow_redirects=False).status_code == 200

    cadastro_service.alternar_status_admin(novo.id, cenario["admin"])
    db.session.commit()

    # a sessão que já estava aberta não pode mais usar a área administrativa
    r = sessao_aberta.get(f"{BASE_URL}/admin/", allow_redirects=False)
    assert r.status_code in (302, 303) and "/login" in r.headers["Location"]
    # nem consegue reativar a si mesmo
    sessao_aberta.post(f"{BASE_URL}/admin/admins/{novo.id}/status")
    assert _recarregar(novo).ativo is False
    # e um login novo é recusado
    r = requests.post(f"{BASE_URL}/login", data={"email": "rv_admin@t.com", "senha": SENHA_PADRAO},
                      allow_redirects=False)
    assert r.status_code == 200, "login de admin desativado deveria ser recusado"


@pytest.mark.regra("RN-015")
def test_hospital_desativado_perde_a_sessao_aberta(cenario):
    from app import db
    from app.services import cadastro_service

    h = cadastro_service.criar_hospital({
        "nome": "Hospital Revisão Desativa", "endereco": "SGAN 605, Brasília - DF",
        "latitude": "-15.77", "longitude": "-47.89", "capacidade_maxima": "5", "tem_garagem": "on",
        "tem_heliponto": "", "responsavel_nome": "Resp D", "email": "rv_hosp_d@t.com",
        "senha": SENHA_PADRAO}, cenario["admin"])
    db.session.commit()
    s = _sessao("rv_hosp_d@t.com")
    assert _logado(s)

    cadastro_service.alternar_status_hospital(h.id, cenario["admin"])
    db.session.commit()
    assert not _logado(s), "sessão de hospital desativado continuou valendo"


@pytest.mark.regra("RN-014")
def test_socorrista_inativo_nao_seleciona_hospital(cenario):
    from app import db
    from app.services import cadastro_service

    o = _ocorrencia(cenario["soc2"])
    s = _sessao("rv_soc2@t.com")
    cadastro_service.alternar_status_socorrista(cenario["soc2"].id, cenario["admin"])
    db.session.commit()
    try:
        s.post(f"{BASE_URL}/ocorrencias/{o.id}/selecionar-hospital",
               data={"hospital_id": cenario["hosp_a"].id})
        assert _recarregar(o).hospital_id is None, "socorrista inativo conseguiu escolher hospital"
    finally:
        cadastro_service.alternar_status_socorrista(cenario["soc2"].id, cenario["admin"])
        db.session.commit()


# ------------------------------------------------------------ 2. CSRF

def test_post_de_outro_site_e_recusado(cenario):
    s = _sessao("admin0@t.com")
    r = s.post(f"{BASE_URL}/admin/admins/novo",
               data={"nome": "Invasor", "email": "rv_invasor@t.com", "senha": "Senha@123"},
               headers={"Origin": "https://site-malicioso.example"}, allow_redirects=False)
    assert r.status_code == 403
    from app.models.usuario import Usuario
    from app import db
    db.session.expire_all()
    assert Usuario.query.filter_by(email="rv_invasor@t.com").first() is None


def test_cookie_de_sessao_tem_samesite(cenario):
    r = requests.post(f"{BASE_URL}/login", data={"email": "rv_soc@t.com", "senha": SENHA_PADRAO},
                      allow_redirects=False)
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


# ------------------------------------- 3. estado da ocorrência no servidor

@pytest.mark.regra("RN-016")
def test_nao_troca_hospital_de_ocorrencia_finalizada_nem_em_trajeto(cenario):
    from app.models.mensagem import Mensagem
    from app import db

    finalizada = _ocorrencia(cenario["soc"], cenario["hosp_a"], status="finalizada",
                             chegada_confirmada_em=datetime.utcnow(), finalizado_em=datetime.utcnow(),
                             desfecho="Alta")
    db.session.add(Mensagem(ocorrencia_id=finalizada.id, remetente_id=cenario["hosp_a"].usuario_id,
                            conteudo="Conversa sigilosa com o hospital A"))
    db.session.commit()
    em_trajeto = _ocorrencia(cenario["soc"], cenario["hosp_a"], status="em_transporte",
                             trajeto_iniciado_em=datetime.utcnow())
    s = _sessao("rv_soc@t.com")
    for o in (finalizada, em_trajeto):
        s.post(f"{BASE_URL}/ocorrencias/{o.id}/selecionar-hospital",
               data={"hospital_id": cenario["hosp_b"].id})
        atual = _recarregar(o)
        assert atual.hospital_id == cenario["hosp_a"].id, f"hospital trocado na ocorrência {atual.status}"
    assert _recarregar(finalizada).status.value == "finalizada"


def test_finalizada_nao_aceita_nova_finalizacao_paciente_nem_localizacao(cenario):
    o = _ocorrencia(cenario["soc"], cenario["hosp_a"], status="finalizada",
                    chegada_confirmada_em=datetime.utcnow(), finalizado_em=datetime.utcnow(),
                    desfecho="Desfecho original")
    s = _sessao("rv_soc@t.com")
    s.post(f"{BASE_URL}/ocorrencias/{o.id}/finalizar", data={"desfecho": "Reescrito"})
    s.post(f"{BASE_URL}/ocorrencias/{o.id}/pacientes/novo",
           data={"nome": "Paciente tardio", "motivo_chamado": "x"})
    s.post(f"{BASE_URL}/ocorrencias/{o.id}/localizacao", json={"lat": -15.0, "lng": -47.0})
    atual = _recarregar(o)
    assert atual.desfecho == "Desfecho original"
    assert len(atual.pacientes) == 1
    assert atual.latitude_atual == pytest.approx(-15.7942)


# ----------------------------------------- 4. sala do WebSocket após troca

@pytest.mark.eventos_ws("localizacao_atualizada")
def test_hospital_abandonado_deixa_de_receber_a_posicao(cenario):
    o = _ocorrencia(cenario["soc"], cenario["hosp_a"], status="em_transporte")
    hosp = _sessao("rv_hosp_a@t.com")
    soc = _sessao("rv_soc@t.com")

    recebidos = []
    cliente = sio_client.Client(reconnection=False)
    cliente.on("localizacao_atualizada", lambda d: recebidos.append(d))
    cliente.connect(BASE_URL, headers={"Cookie": f"session={hosp.cookies['session']}"})
    cliente.emit("entrar_sala_ocorrencia", {"ocorrencia_id": o.id})
    cliente.sleep(0.5)

    soc.post(f"{BASE_URL}/ocorrencias/{o.id}/trocar-hospital")
    soc.post(f"{BASE_URL}/ocorrencias/{o.id}/selecionar-hospital", data={"hospital_id": cenario["hosp_b"].id})

    socorrista = sio_client.Client(reconnection=False)
    socorrista.connect(BASE_URL, headers={"Cookie": f"session={soc.cookies['session']}"})
    socorrista.emit("entrar_sala_ocorrencia", {"ocorrencia_id": o.id})
    socorrista.emit("atualizar_localizacao", {"ocorrencia_id": o.id, "lat": -15.80, "lng": -47.90})
    socorrista.sleep(1.0)
    cliente.disconnect()
    socorrista.disconnect()
    assert recebidos == [], "o hospital A continuou recebendo a posição depois da troca"


# ---------------------------------------------- 5. validação do prontuário

@pytest.mark.parametrize("campo,valor", [
    ("idade", "aproximadamente 45 anos"),       # 24 caracteres; coluna tem 20
    ("cpf", "123.456.789-000000"),
    ("pressao_arterial", "120/80 mmHg em repouso"),
    ("nivel_consciencia", "x" * 101),
    ("frequencia_cardiaca", "99999999999"),
    ("saturacao_o2", "-5"),
    ("saturacao_o2", "150"),
    ("glasgow", "20"),
    ("temperatura", "nan"),
])
def test_prontuario_com_valor_fora_do_limite_e_recusado_sem_erro_500(cenario, campo, valor):
    o = _ocorrencia(cenario["soc"])
    s = _sessao("rv_soc@t.com")
    dados = {"nome": "Paciente limite", "motivo_chamado": "Teste de limite", campo: valor}
    r = s.post(f"{BASE_URL}/ocorrencias/{o.id}/pacientes/novo", data=dados)
    assert r.status_code == 200, f"{campo}={valor!r} gerou {r.status_code}"
    assert len(_recarregar(o).pacientes) == 1, f"{campo}={valor!r} foi aceito"


def test_foto_nao_some_quando_a_edicao_falha(cenario):
    o = _ocorrencia(cenario["soc"])
    s = _sessao("rv_soc@t.com")
    pac = _recarregar(o).pacientes[0]
    url = f"{BASE_URL}/ocorrencias/{o.id}/pacientes/{pac.id}/editar"
    base = {"nome": "Paciente Revisão", "motivo_chamado": "Queda"}
    s.post(url, data=base, files={"anexos": ("foto.jpg", _foto(), "image/jpeg")})
    anexo = _recarregar(pac).anexos[0]

    # remove a foto e, no mesmo envio, manda um campo inválido -> nada pode mudar
    s.post(url, data={**base, "remover_anexo": str(anexo.id), "idade": "x" * 30})
    assert len(_recarregar(pac).anexos) == 1
    r = s.get(f"{BASE_URL}/ocorrencias/{o.id}/anexos/{anexo.id}")
    assert r.status_code == 200 and r.headers["Content-Type"].startswith("image/")


# ------------------------------------------------- 6. concorrência RN-006

@pytest.mark.regra("RN-006")
def test_dois_socorristas_ao_mesmo_tempo_nao_lotam_alem_da_capacidade(cenario):
    o1 = _ocorrencia(cenario["soc"])
    o2 = _ocorrencia(cenario["soc2"])
    s1, s2 = _sessao("rv_soc@t.com"), _sessao("rv_soc2@t.com")
    hid = cenario["hosp_um_leito"].id
    ids = (o1.id, o2.id)  # lidos aqui: as threads não têm contexto do app
    barreira = threading.Barrier(2)

    def escolher(s, oid):
        barreira.wait()
        s.post(f"{BASE_URL}/ocorrencias/{oid}/selecionar-hospital", data={"hospital_id": hid})

    threads = [threading.Thread(target=escolher, args=a) for a in ((s1, ids[0]), (s2, ids[1]))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    destinos = [_recarregar(o1).hospital_id, _recarregar(o2).hospital_id]
    assert destinos.count(hid) == 1, "hospital de 1 leito recebeu as duas emergências"


# --------------------------------------------- 7. configuração insegura

def test_sem_secret_key_o_app_nao_usa_chave_fixa():
    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    r = subprocess.run(
        [sys.executable, "-c",
         "import os; os.chdir('/'); "
         f"import sys; sys.path.insert(0, {BACKEND_DIR!r}); "
         "from app.config.config import Config; print(Config.SECRET_KEY)"],
        env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    chave = r.stdout.strip()
    assert chave != "dev-secret-key" and len(chave) >= 32


def test_run_py_nao_liga_debug_por_padrao():
    with open(os.path.join(BACKEND_DIR, "run.py"), encoding="utf-8") as f:
        assert "debug=True" not in f.read()


# ---------------------------------------------------------- 8. XSS

def test_nome_de_hospital_com_script_nao_quebra_a_pagina(cenario):
    from app import db
    from app.services import cadastro_service

    cadastro_service.criar_hospital({
        "nome": "Hospital </script><img src=x onerror=alert(1)>", "endereco": "SQS 102, Brasília - DF",
        "latitude": "-15.81", "longitude": "-47.90", "capacidade_maxima": "5", "tem_garagem": "on",
        "tem_heliponto": "", "responsavel_nome": "Resp X", "email": "rv_hosp_xss@t.com",
        "senha": SENHA_PADRAO}, cenario["admin"])
    db.session.commit()
    o = _ocorrencia(cenario["soc"])
    html = _sessao("rv_soc@t.com").get(f"{BASE_URL}/ocorrencias/{o.id}/hospitais").text
    assert "</script><img" not in html


# ---------------------------------------------- 9. entradas que davam 500

def test_entradas_malformadas_nao_geram_erro_500(cenario):
    o = _ocorrencia(cenario["soc"])
    soc = _sessao("rv_soc@t.com")
    hosp = _sessao("rv_hosp_a@t.com")
    casos = [
        (soc, "post", f"/ocorrencias/{o.id}/selecionar-hospital", {"data": {"hospital_id": "abc"}}),
        (soc, "post", f"/ocorrencias/{o.id}/selecionar-hospital", {"data": {"hospital_id": "99999999999"}}),
        (soc, "post", f"/ocorrencias/{o.id}/localizacao", {"json": {"lat": "inf", "lng": 0}}),
        (soc, "post", f"/ocorrencias/{o.id}/localizacao", {"json": {"lat": 999, "lng": 0}}),
        (hosp, "get", "/emergencias/historico?data_fim=9999-12-31", {}),
        (hosp, "get", "/emergencias/historico?data_inicio=0001-01-01", {}),
        (hosp, "get", "/emergencias/historico?busca=%C2%B2", {}),
        (hosp, "get", "/emergencias/historico/exportar?data_fim=9999-12-31", {}),
        (soc, "post", "/perfil", {"data": {"nome": "x" * 300, "email": "rv_soc@t.com"}}),
    ]
    for sessao, metodo, rota, kw in casos:
        r = getattr(sessao, metodo)(f"{BASE_URL}{rota}", **kw)
        assert r.status_code < 500, f"{metodo.upper()} {rota} {kw} -> {r.status_code}"
    assert _recarregar(o).latitude_atual == pytest.approx(-15.7942), "coordenada absurda foi gravada"


# ------------------------------------------------- 10. CSV

def test_csv_neutraliza_formula(cenario):
    from app import db

    o = _ocorrencia(cenario["soc"], cenario["hosp_a"], status="em_transporte")
    o.local = '=HYPERLINK("http://malicioso.example","Clique")'
    db.session.commit()
    csv_texto = _sessao("rv_hosp_a@t.com").get(f"{BASE_URL}/emergencias/historico/exportar").text
    linha = next(l for l in csv_texto.splitlines() if "HYPERLINK" in l)
    celula_local = linha.split(";")[4].strip('"')
    assert celula_local.startswith("'="), linha


# ------------------------------------------- 11. prioridade (RN-010)

@pytest.mark.regra("RN-010")
def test_prioridade_calculada_pelo_servidor_e_criticos_primeiro(cenario):
    """A prioridade nunca é digitada: sai dos sinais vitais, nesta ordem
    (PCR, Glasgow < 8, saturação < 90 -> crítica; agravamento -> alta;
    senão média), e a lista mostra os críticos primeiro."""
    o = _ocorrencia(cenario["soc"])  # já vem com 1 paciente "média"
    s = _sessao("rv_soc@t.com")
    casos = [
        ("Paciente Agravou", {"agravamento_registrado": "on"}, "alta"),
        ("Paciente Saturação", {"saturacao_o2": "85"}, "critica"),
        ("Paciente Glasgow", {"glasgow": "6"}, "critica"),
        ("Paciente PCR", {"parada_cardiorrespiratoria": "on", "prioridade": "media"}, "critica"),
        ("Paciente Limite", {"saturacao_o2": "90", "glasgow": "8"}, "media"),
    ]
    for nome, campos, _ in casos:
        s.post(f"{BASE_URL}/ocorrencias/{o.id}/pacientes/novo",
               data={"nome": nome, "motivo_chamado": "Teste RN-010", **campos})
    pacientes = {p.nome: p.prioridade.value for p in _recarregar(o).pacientes}
    for nome, _, esperada in casos:
        assert pacientes[nome] == esperada, f"{nome}: {pacientes[nome]} (esperado {esperada})"

    html = s.get(f"{BASE_URL}/ocorrencias/{o.id}/pacientes").text
    posicoes = {nome: html.find(nome) for nome in pacientes}
    criticos = [posicoes[n] for n, _, p in casos if p == "critica"]
    outros = [posicoes[n] for n in ("Paciente Agravou", "Paciente Limite", "Paciente Revisão")]
    assert max(criticos) < min(outros), "pacientes críticos não aparecem primeiro"


# ------------------------------------- 12. volume: painel e inbox (7.2.8)

def test_painel_e_inbox_continuam_leves_com_muitos_atendimentos(cenario):
    """Com 120 atendimentos finalizados, o painel mostra só os 30 mais
    recentes, e o inbox as 100 conversas mais recentes MAIS a conversa
    antiga que ainda tem mensagem não lida (não pode sumir)."""
    from datetime import timedelta

    from app import db
    from app.models.mensagem import Mensagem
    from app.services.chat_service import CONVERSAS_NO_INBOX
    from app.services.painel_service import FINALIZADAS_NO_PAINEL

    hosp, soc = cenario["hosp_b"], cenario["soc2"]
    base = datetime.utcnow() - timedelta(days=200)
    ids = []
    for i in range(120):
        quando = base + timedelta(hours=i)
        o = _ocorrencia(soc, hosp, status="finalizada", criado_em=quando, chegada_confirmada_em=quando,
                        finalizado_em=quando + timedelta(minutes=30), desfecho="ok", chat_encerrado_em=quando)
        db.session.add(Mensagem(ocorrencia_id=o.id, remetente_id=hosp.usuario_id, conteudo=f"msg {o.id}",
                                enviado_em=quando, lida=(i != 0)))  # só a MAIS ANTIGA tem não lida
        ids.append(o.id)
    db.session.commit()

    s = _sessao("rv_hosp_b@t.com")
    painel = s.get(f"{BASE_URL}/dashboard").text
    assert sum(f'data-id="{oid}"' in painel for oid in ids) == FINALIZADAS_NO_PAINEL
    assert f'data-id="{ids[-1]}"' in painel and f'data-id="{ids[0]}"' not in painel

    inbox = _sessao("rv_soc2@t.com").get(f"{BASE_URL}/inbox/").text
    presentes = [oid for oid in ids if f"Ocorrência #{oid}<" in inbox or f"Ocorrência #{oid} " in inbox
                 or f"#{oid}\"" in inbox or f"/inbox/{oid}\"" in inbox]
    assert ids[0] in presentes, "conversa antiga com mensagem não lida sumiu do inbox"
    assert ids[-1] in presentes
    assert ids[1] not in presentes, "inbox não limitou às conversas mais recentes"
    assert len(presentes) == CONVERSAS_NO_INBOX + 1


# --------------------- 13. ocorrência aberta pelo app com o formulário web aberto

def test_web_avisa_quando_ja_existe_ocorrencia_aberta_pelo_app(cenario):
    """Formulário web aberto + ocorrência de ambulância criada pelo app:
    ao enviar helicóptero, a web não cria outra e AVISA o motivo, em vez de
    levar o socorrista calado para a ocorrência de ambulância."""
    from app.models.ocorrencia import Ocorrencia
    from app import db
    from app.services import cadastro_service

    cadastro_service.criar_socorrista({
        "nome": "Socorrista Web e App", "matricula": "RV-0003", "telefone": "61999990003",
        "email": "rv_soc3@t.com", "senha": SENHA_PADRAO}, cenario["admin"])
    db.session.commit()
    web = _sessao("rv_soc3@t.com")
    assert web.get(f"{BASE_URL}/ocorrencias/novo").status_code == 200   # formulário aberto
    tok = requests.post(f"{BASE_URL}/api/v1/login", json={"email": "rv_soc3@t.com", "senha": SENHA_PADRAO}).json()["token"]
    pelo_app = requests.post(f"{BASE_URL}/api/v1/ocorrencias", headers={"Authorization": f"Bearer {tok}"},
                             json={"local": "Aberta pelo app", "veiculo": "ambulancia"}).json()
    try:
        r = web.post(f"{BASE_URL}/ocorrencias/novo",
                     data={"local": "Pedido de helicóptero na web", "veiculo": "helicoptero"})
        assert f"/ocorrencias/{pelo_app['id']}" in r.url
        assert "Você já tem uma ocorrência em andamento" in r.text and "Ambulância" in r.text
        db.session.expire_all()
        assert Ocorrencia.query.filter_by(local="Pedido de helicóptero na web").count() == 0
    finally:
        db.session.rollback()


@pytest.mark.parametrize("tipo, valor, esperado", [
    ("pa", "180/110", "alto"), ("pa", "120/80", "normal"), ("pa", "85/50", "baixo"), ("pa", "12x8", None),
    ("fc", 88, "normal"), ("fc", 130, "alto"), ("fc", 45, "baixo"),
    ("fr", 18, "normal"), ("fr", 28, "alto"),
    ("spo2", 95, "normal"), ("spo2", 88, "baixo"),
    ("temp", 36.6, "normal"), ("temp", "38,4", "alto"), ("temp", 34.9, "baixo"),
    ("glasgow", 15, "normal"), ("glasgow", 13, "baixo"),
    ("fc", None, None), ("fc", "", None),
])
def test_sinais_vitais_fora_da_faixa_sao_sinalizados(db_app, tipo, valor, esperado):
    from app.services.sinais_vitais import avaliar

    estado, referencia = avaliar(tipo, valor)
    assert estado == esperado
    assert referencia   # a faixa de referência sempre aparece no cartão


def test_numeros_no_padrao_brasileiro(db_app):
    filtros = db_app.jinja_env.filters
    assert filtros["km"](12.48) == "12,5 km"
    assert filtros["minutos"](3.4) == "3 min"
    assert filtros["minutos"](0.2) == "1 min"           # nunca "0 min" com a viatura a caminho
    assert filtros["decimal"](36.6) == "36,6"
    assert filtros["duracao"](524.6) == "8h 45min"
    assert filtros["duracao"](41) == "41 min"
    assert filtros["km"](None) == filtros["minutos"](None) == "—"


def test_atras_de_proxy_https_o_login_funciona_e_csrf_continua(db_app, monkeypatch):
    """Hospedado atrás de proxy HTTPS (ATRAS_DE_PROXY=1): o POST que vem de
    https://dominio é aceito, o de outro site continua recusado e o cookie de
    sessão só trafega por HTTPS."""
    from app import create_app
    from app.config.config import Config

    proxy = {"Host": "orbis.exemplo.com.br", "X-Forwarded-Proto": "https"}
    dados = {"email": "ninguem@t.com", "senha": "errada"}

    # sem a opção: o Flask se vê como http:// e recusa o login vindo de https://
    sem = create_app().test_client()
    assert sem.post("/login", data=dados, headers={**proxy, "Origin": "https://orbis.exemplo.com.br"}).status_code == 403

    monkeypatch.setattr(Config, "ATRAS_DE_PROXY", True)
    app = create_app()
    assert app.config["SESSION_COOKIE_SECURE"] is True
    com = app.test_client()
    assert com.post("/login", data=dados, headers={**proxy, "Origin": "https://orbis.exemplo.com.br"}).status_code != 403
    assert com.post("/login", data=dados, headers={**proxy, "Origin": "https://site-malicioso.com"}).status_code == 403
