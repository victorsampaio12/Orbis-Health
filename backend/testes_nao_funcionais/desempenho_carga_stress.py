"""
7.2.5 Perfil de desempenho, 7.2.6 Carga e 7.2.7 Stress.

Roda contra um ambiente descartável populado com os dados de Brasília
(seed_demo.py). Mede:

- desempenho: tempo de resposta de cada tela principal, por perfil, com
  um único usuário (30 requisições por rota, depois de 3 de aquecimento);
- carga: usuários virtuais simultâneos (1, 5, 10, 25, 50) navegando pelo
  roteiro típico do hospital e do socorrista durante 20 s cada;
- stress: 100 e 200 usuários simultâneos, rajada de logins, envio acima do
  limite (413), imagem "bomba de descompressão" e 150 conexões WebSocket
  ao mesmo tempo. Depois de cada etapa, confere se o servidor continua
  respondendo.

Uso:  python testes_nao_funcionais/desempenho_carga_stress.py
"""
import io
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import socketio
from PIL import Image

from ambiente import ADMIN_EMAIL, ADMIN_SENHA, Ambiente, salvar_resultado

HOSPITAL = "hbdf@orbishealth.com"


def pct(valores, p):
    if not valores:
        return None
    valores = sorted(valores)
    k = max(0, min(len(valores) - 1, round(p / 100 * (len(valores) - 1))))
    return round(valores[k] * 1000, 1)


def resumo(tempos, erros=0, total=None):
    total = total if total is not None else len(tempos) + erros
    return {
        "requisicoes": total,
        "erros": erros,
        "taxa_erro_pct": round(100 * erros / total, 2) if total else 0,
        "media_ms": round(statistics.mean(tempos) * 1000, 1) if tempos else None,
        "p50_ms": pct(tempos, 50),
        "p95_ms": pct(tempos, 95),
        "p99_ms": pct(tempos, 99),
        "max_ms": round(max(tempos) * 1000, 1) if tempos else None,
    }


def descobrir_dados(amb):
    """Uma ocorrência do Hospital de Base com paciente, e o socorrista dono."""
    _, linha = amb.psql(
        "SELECT o.id, u.email, p.id FROM ocorrencia o "
        "JOIN hospital h ON h.id = o.hospital_id JOIN usuario hu ON hu.id = h.usuario_id "
        "JOIN socorrista s ON s.id = o.socorrista_id JOIN usuario u ON u.id = s.usuario_id "
        "JOIN paciente p ON p.ocorrencia_id = o.id "
        f"WHERE hu.email = '{HOSPITAL}' ORDER BY o.id LIMIT 1"
    )
    oc, soc_email, pac = linha.split("|")
    return int(oc), soc_email, int(pac)


def ocorrencia_aberta(amb):
    """Um socorrista livre abre uma ocorrência: é a única situação em que a
    tela de escolha de hospital (que calcula a lotação de todos) responde."""
    _, email = amb.psql(
        "SELECT u.email FROM usuario u JOIN socorrista s ON s.usuario_id=u.id WHERE u.ativo AND NOT EXISTS "
        "(SELECT 1 FROM ocorrencia o WHERE o.socorrista_id=s.id AND o.status<>'finalizada') LIMIT 1")
    s = amb.sessao(email)
    s.post(amb.url + "/ocorrencias/novo", data={"local": "Setor Comercial Sul, Brasília", "veiculo": "ambulancia",
                                                "latitude": "-15.80", "longitude": "-47.89"})
    _, oid = amb.psql("SELECT max(o.id) FROM ocorrencia o JOIN socorrista s ON s.id=o.socorrista_id "
                      f"JOIN usuario u ON u.id=s.usuario_id WHERE u.email='{email}'")
    return int(oid), email


def rotas_por_perfil(oc, aberta):
    return {
        "anonimo": ["/login"],
        "admin": ["/admin/", "/admin/dashboard-dados", "/admin/hospitais", "/admin/socorristas",
                  "/admin/admins"],
        "socorrista": [f"/ocorrencias/{oc}", f"/ocorrencias/{oc}/pacientes",
                       f"/ocorrencias/{oc}/prontuario", f"/ocorrencias/{oc}/pacientes/novo",
                       f"/ocorrencias/{oc}/mensagens", "/inbox/", "/perfil"],
        "socorrista_livre": [f"/ocorrencias/{aberta}/hospitais", "/ocorrencias/novo"],
        "hospital": ["/dashboard", f"/ocorrencias/{oc}", f"/ocorrencias/{oc}/prontuario",
                     f"/ocorrencias/{oc}/relatorio", "/emergencias/historico",
                     "/emergencias/historico/exportar", "/inbox/"],
    }


def medir_rota(sessao, url, n=30):
    for _ in range(3):
        sessao.get(url)
    tempos, status = [], set()
    for _ in range(n):
        t = time.perf_counter()
        r = sessao.get(url, allow_redirects=False)
        tempos.append(time.perf_counter() - t)
        status.add(r.status_code)
    return {**resumo(tempos), "status": sorted(status), "bytes": len(r.content)}


def perfil_desempenho(amb, oc, soc_email):
    aberta, livre = ocorrencia_aberta(amb)
    sessoes = {
        "anonimo": requests.Session(),
        "admin": amb.sessao(ADMIN_EMAIL, ADMIN_SENHA),
        "socorrista": amb.sessao(soc_email),
        "socorrista_livre": amb.sessao(livre),
        "hospital": amb.sessao(HOSPITAL),
    }
    resultado = {}
    for perfil, rotas in rotas_por_perfil(oc, aberta).items():
        for rota in rotas:
            m = medir_rota(sessoes[perfil], amb.url + rota)
            resultado[f"{perfil} GET {rota}"] = m
            print(f"  {perfil:16} {rota:40} p50={m['p50_ms']:>7} ms  p95={m['p95_ms']:>7} ms  {m['status']}")

    # login: custo do bcrypt
    tempos = []
    for _ in range(10):
        t = time.perf_counter()
        requests.post(amb.url + "/login", data={"email": HOSPITAL, "senha": "Senha@123"}, allow_redirects=False)
        tempos.append(time.perf_counter() - t)
    resultado["anonimo POST /login (bcrypt)"] = resumo(tempos)
    print(f"  login POST p50={resultado['anonimo POST /login (bcrypt)']['p50_ms']} ms")
    return resultado


def usuario_virtual(amb, perfil, email, roteiro, fim, tempos, erros, trava, timeout=30):
    try:
        s = amb.sessao(email) if perfil != "admin" else amb.sessao(ADMIN_EMAIL, ADMIN_SENHA)
    except Exception:
        with trava:
            erros.append("login")
        return
    i = 0
    while time.monotonic() < fim:
        url = amb.url + roteiro[i % len(roteiro)]
        i += 1
        t = time.perf_counter()
        try:
            r = s.get(url, allow_redirects=False, timeout=timeout)
            ok = r.status_code == 200
        except requests.RequestException:
            ok = False
        dt = time.perf_counter() - t
        with trava:
            (tempos.append(dt) if ok else erros.append(url))


def rodada(amb, n_usuarios, duracao, oc, soc_email):
    roteiro_hosp = ["/dashboard", f"/ocorrencias/{oc}", f"/ocorrencias/{oc}/prontuario",
                    "/emergencias/historico", "/inbox/"]
    roteiro_soc = [f"/ocorrencias/{oc}", f"/ocorrencias/{oc}/pacientes", f"/ocorrencias/{oc}/prontuario",
                   f"/ocorrencias/{oc}/mensagens", "/inbox/"]
    tempos, erros, trava = [], [], threading.Lock()
    inicio = time.monotonic()
    fim = inicio + duracao
    with ThreadPoolExecutor(max_workers=n_usuarios) as ex:
        for k in range(n_usuarios):
            if k % 2 == 0:
                ex.submit(usuario_virtual, amb, "hospital", HOSPITAL, roteiro_hosp, fim, tempos, erros, trava)
            else:
                ex.submit(usuario_virtual, amb, "socorrista", soc_email, roteiro_soc, fim, tempos, erros, trava)
    decorrido = time.monotonic() - inicio
    r = resumo(tempos, len(erros))
    r["usuarios"] = n_usuarios
    r["duracao_s"] = round(decorrido, 1)
    r["vazao_req_s"] = round(len(tempos) / decorrido, 1)
    return r


def servidor_vivo(amb):
    try:
        return requests.get(amb.url + "/login", timeout=10).status_code == 200
    except requests.RequestException:
        return False


def carga(amb, oc, soc_email):
    resultado = []
    for n in (1, 5, 10, 25, 50):
        r = rodada(amb, n, 20, oc, soc_email)
        resultado.append(r)
        print(f"  {n:>3} usuários: {r['vazao_req_s']:>6} req/s  p50={r['p50_ms']} p95={r['p95_ms']} "
              f"erros={r['taxa_erro_pct']}%")
    return resultado


def stress(amb, oc, soc_email, pac):
    resultado = {"concorrencia": []}
    for n in (100, 200):
        r = rodada(amb, n, 20, oc, soc_email)
        r["servidor_respondendo_depois"] = servidor_vivo(amb)
        resultado["concorrencia"].append(r)
        print(f"  {n:>3} usuários: {r['vazao_req_s']} req/s  p95={r['p95_ms']} erros={r['taxa_erro_pct']}% "
              f"vivo={r['servidor_respondendo_depois']}")

    # rajada de logins simultâneos (bcrypt consome CPU)
    def um_login(_):
        t = time.perf_counter()
        try:
            r = requests.post(amb.url + "/login", data={"email": HOSPITAL, "senha": "Senha@123"},
                              allow_redirects=False, timeout=60)
            return time.perf_counter() - t, r.status_code in (302, 303)
        except requests.RequestException:
            return time.perf_counter() - t, False
    with ThreadPoolExecutor(max_workers=50) as ex:
        res = list(ex.map(um_login, range(50)))
    tempos = [t for t, ok in res if ok]
    resultado["rajada_50_logins"] = resumo(tempos, sum(1 for _, ok in res if not ok))
    print(f"  50 logins simultâneos: p95={resultado['rajada_50_logins']['p95_ms']} ms "
          f"erros={resultado['rajada_50_logins']['erros']}")

    soc = amb.sessao(soc_email)
    url_edit = f"{amb.url}/ocorrencias/{oc}/pacientes/{pac}/editar"

    # envio acima de MAX_CONTENT_LENGTH (60 MB)
    grande = b"\0" * (61 * 1024 * 1024)
    t = time.perf_counter()
    try:
        r = soc.post(url_edit, files={"anexos": ("grande.jpg", grande, "image/jpeg")},
                     data={"nome": "x"}, allow_redirects=False, timeout=60)
        resultado["envio_61MB"] = {"status": r.status_code, "tempo_ms": round((time.perf_counter() - t) * 1000)}
    except requests.RequestException as e:
        resultado["envio_61MB"] = {"erro": type(e).__name__, "tempo_ms": round((time.perf_counter() - t) * 1000)}
    resultado["envio_61MB"]["servidor_respondendo_depois"] = servidor_vivo(amb)
    print(f"  envio 61 MB: {resultado['envio_61MB']}")

    # bomba de descompressão: PNG pequeno em disco, enorme em memória
    for lado in (12000, 20000):
        buf = io.BytesIO()
        Image.new("L", (lado, lado)).save(buf, "PNG", optimize=True)
        t = time.perf_counter()
        try:
            r = soc.post(url_edit, files={"anexos": (f"bomba{lado}.png", buf.getvalue(), "image/png")},
                         data={"nome": "x"}, allow_redirects=True, timeout=120)
            corpo = r.text
            resultado[f"bomba_{lado}px"] = {
                "arquivo_kb": round(len(buf.getvalue()) / 1024),
                "status": r.status_code,
                "recusada": "não é uma imagem" in corpo or "formato" in corpo.lower(),
                "tempo_ms": round((time.perf_counter() - t) * 1000),
            }
        except requests.RequestException as e:
            resultado[f"bomba_{lado}px"] = {"erro": type(e).__name__}
        resultado[f"bomba_{lado}px"]["servidor_respondendo_depois"] = servidor_vivo(amb)
        print(f"  bomba {lado}x{lado}: {resultado[f'bomba_{lado}px']}")

    # 150 conexões WebSocket simultâneas do hospital
    cookie = "; ".join(f"{k}={v}" for k, v in amb.sessao(HOSPITAL).cookies.items())
    conectados, recebidos, falhas = [], [], []
    trava = threading.Lock()

    def cliente(_):
        c = socketio.Client(reconnection=False)
        try:
            c.connect(amb.url, headers={"Cookie": cookie}, wait_timeout=20)
            c.emit("entrar_sala_ocorrencia", {"ocorrencia_id": oc})
            with trava:
                conectados.append(c)
        except Exception as e:
            with trava:
                falhas.append(type(e).__name__)

    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=50) as ex:
        list(ex.map(cliente, range(150)))
    resultado["websocket_150"] = {
        "conectados": len(conectados), "falhas": len(falhas),
        "tempo_total_ms": round((time.perf_counter() - t) * 1000),
        "servidor_respondendo_com_conexoes_abertas": servidor_vivo(amb),
    }
    for c in conectados:
        try:
            c.disconnect()
        except Exception:
            pass
    print(f"  150 websockets: {resultado['websocket_150']}")
    resultado["servidor_respondendo_no_fim"] = servidor_vivo(amb)
    return resultado


def main():
    with Ambiente(porta_db=55991, porta_app=5598) as amb:
        oc, soc_email, pac = descobrir_dados(amb)
        print(f"Ocorrência {oc}, socorrista {soc_email}, paciente {pac}")
        print("== Perfil de desempenho ==")
        perf = perfil_desempenho(amb, oc, soc_email)
        print("== Carga ==")
        car = carga(amb, oc, soc_email)
        print("== Stress ==")
        stre = stress(amb, oc, soc_email, pac)
        salvar_resultado("desempenho_carga_stress", {
            "desempenho": perf, "carga": car, "stress": stre,
            "servidor": "Werkzeug + Flask-SocketIO (threading), 1 processo",
        })


if __name__ == "__main__":
    main()
