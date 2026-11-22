"""
7.2.10 Tolerância a falhas e recuperação.

Cenários:
1. Servidor morto (kill -9) no meio de um trajeto: ao voltar, o trajeto é
   retomado na posição certa quando o hospital abre o painel.
2. Banco de dados reiniciado com o servidor no ar: quantas requisições
   falham até a aplicação voltar a funcionar sozinha (sem reiniciar).
3. OSRM fora do ar (conexão recusada) e lento (não responde): a geração de
   rota falha com mensagem, em tempo limitado, sem corromper a ocorrência.
4. Nominatim fora do ar: cadastro de hospital e autocomplete continuam
   respondendo (sem erro 500).
5. Backup e restauração do banco (pg_dump / pg_restore) com conferência
   das contagens.

Uso:  python testes_nao_funcionais/recuperacao.py
"""
import http.server
import socketserver
import subprocess
import threading
import time

import requests

from ambiente import ADMIN_EMAIL, ADMIN_SENHA, Ambiente, salvar_resultado
from desempenho_carga_stress import HOSPITAL

PORTA_LENTA = 5591


def posicao(amb, oid):
    _, linha = amb.psql(f"SELECT latitude_atual||','||longitude_atual FROM ocorrencia WHERE id={oid}")
    return tuple(float(x) for x in linha.split(","))


def queda_no_trajeto(amb):
    # trajeto longo e recém-iniciado de uma ocorrência a caminho do HBDF
    _, oid = amb.psql(
        "SELECT o.id FROM ocorrencia o JOIN hospital h ON h.id=o.hospital_id JOIN usuario u ON u.id=h.usuario_id "
        f"WHERE u.email='{HOSPITAL}' AND o.status='em_transporte' AND o.rota_geometria IS NOT NULL "
        "AND o.chegada_confirmada_em IS NULL LIMIT 1")
    amb.psql(f"UPDATE ocorrencia SET trajeto_iniciado_em = (now() at time zone 'utc') - interval '20 seconds', "
             f"trajeto_duracao_s = 600 WHERE id={oid}")
    hosp = amb.sessao(HOSPITAL)
    hosp.get(amb.url + "/dashboard")  # painel garante a simulação rodando
    time.sleep(6)
    p1 = posicao(amb, oid)
    time.sleep(4)
    p2 = posicao(amb, oid)
    andando_antes = p1 != p2

    amb.derrubar_servidor("kill")          # queda brusca (SIGKILL)
    time.sleep(8)
    parada = posicao(amb, oid)
    time.sleep(3)
    parada_ok = posicao(amb, oid) == parada  # sem servidor ninguém move a viatura

    t = time.perf_counter()
    amb.subir_servidor()
    subida_s = round(time.perf_counter() - t, 1)
    hosp = amb.sessao(HOSPITAL)            # sessões antigas continuam válidas? (mesma SECRET_KEY)
    hosp.get(amb.url + "/dashboard")
    time.sleep(6)
    p3 = posicao(amb, oid)
    time.sleep(4)
    p4 = posicao(amb, oid)
    r = {
        "ocorrencia": int(oid),
        "viatura_andando_antes_da_queda": andando_antes,
        "posicao_congelada_com_servidor_fora": parada_ok,
        "tempo_para_servidor_voltar_s": subida_s,
        "retomou_depois_de_reabrir_o_painel": p3 != parada and p4 != p3,
        "pulou_para_a_posicao_correta_pelo_relogio": p3 != parada,
    }
    print(f"  queda no trajeto: {r}")
    return r


def queda_do_banco(amb):
    hosp = amb.sessao(HOSPITAL)
    assert hosp.get(amb.url + "/dashboard").status_code == 200
    subprocess.run(["docker", "restart", "-t", "1", amb.container], check=True, capture_output=True)
    amb.esperar_banco_pronto()
    status = []
    for _ in range(10):
        try:
            status.append(hosp.get(amb.url + "/dashboard", timeout=15).status_code)
        except requests.RequestException as e:
            status.append(type(e).__name__)
    r = {"respostas_apos_reinicio_do_banco": status,
         "falhas": sum(1 for s in status if s != 200),
         "recuperou_sem_reiniciar_servidor": status[-1] == 200}
    print(f"  queda do banco: {r}")

    # banco totalmente fora: a aplicação responde (erro) ou trava?
    subprocess.run(["docker", "stop", "-t", "1", amb.container], check=True, capture_output=True)
    t = time.perf_counter()
    try:
        fora = hosp.get(amb.url + "/dashboard", timeout=30).status_code
    except requests.RequestException as e:
        fora = type(e).__name__
    r["com_banco_desligado"] = {"status": fora, "tempo_ms": round((time.perf_counter() - t) * 1000)}
    subprocess.run(["docker", "start", amb.container], check=True, capture_output=True)
    amb.esperar_banco_pronto()
    time.sleep(1)
    ok = []
    for _ in range(5):
        try:
            ok.append(hosp.get(amb.url + "/dashboard", timeout=15).status_code)
        except requests.RequestException as e:
            ok.append(type(e).__name__)
    r["depois_de_religar"] = ok
    print(f"  banco desligado: {r['com_banco_desligado']} -> depois {ok}")
    return r


class _Lento(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        time.sleep(30)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def _ocorrencia_com_hospital(amb, soc_email):
    """Cria (via HTTP, como o socorrista) uma ocorrência e escolhe hospital."""
    s = amb.sessao(soc_email)
    _, oid_antes = amb.psql("SELECT coalesce(max(id),0) FROM ocorrencia")
    s.post(amb.url + "/ocorrencias/novo", data={"local": "Rodoviária do Plano Piloto", "veiculo": "ambulancia",
                                                "latitude": "-15.7939", "longitude": "-47.8828"})
    _, oid = amb.psql("SELECT max(id) FROM ocorrencia")
    assert oid != oid_antes, "ocorrência não criada"
    s.post(f"{amb.url}/ocorrencias/{oid}/pacientes/novo", data={"nome": "Paciente Falha", "motivo_chamado": "Queda"})
    _, hid = amb.psql("SELECT id FROM hospital WHERE tem_garagem AND ativo AND capacidade_maxima > "
                      "(SELECT count(*) FROM ocorrencia o WHERE o.hospital_id=hospital.id AND o.status<>'finalizada') "
                      "ORDER BY id LIMIT 1")
    s.post(f"{amb.url}/ocorrencias/{oid}/selecionar-hospital", data={"hospital_id": hid})
    return s, oid


def servicos_externos(amb, socorristas):
    resultado = {}
    servidor_lento = socketserver.ThreadingTCPServer(("localhost", PORTA_LENTA), _Lento)
    threading.Thread(target=servidor_lento.serve_forever, daemon=True).start()
    try:
        cenarios = [("osrm_recusando_conexao", "http://localhost:9"),
                    ("osrm_sem_responder", f"http://localhost:{PORTA_LENTA}")]
        # um socorrista por cenário: cada um só pode ter uma ocorrência ativa
        for (nome, url), soc_email in zip(cenarios, socorristas):
            amb.derrubar_servidor()
            amb.env["OSRM_BASE_URL"] = url
            amb.env["NOMINATIM_BASE_URL"] = url
            amb.subir_servidor()
            s, oid = _ocorrencia_com_hospital(amb, soc_email)
            t = time.perf_counter()
            r = s.post(f"{amb.url}/ocorrencias/{oid}/gerar-rota", timeout=60)
            dt = round(time.perf_counter() - t, 1)
            _, estado = amb.psql(f"SELECT status||'|'||coalesce(hospital_id::text,'-')||'|'||"
                                 f"coalesce(rota_geometria,'SEM ROTA') FROM ocorrencia WHERE id={oid}")
            st, hosp, rota = estado.split("|", 2)
            msg = next((m for m in ("Não foi possível", "indisponível", "tente novamente", "rota")
                        if m.lower() in r.text.lower()), None)
            resultado[nome] = {
                "status_http": r.status_code, "tempo_s": dt, "mensagem_ao_usuario": msg is not None,
                "ocorrencia_status": st, "hospital_mantido": hosp != "-", "rota_gravada": rota != "SEM ROTA",
            }
            # Nominatim fora: telas de cadastro de hospital
            adm = amb.sessao(ADMIN_EMAIL, ADMIN_SENHA)
            t = time.perf_counter()
            g = adm.get(f"{amb.url}/admin/geocodificar?endereco=SQS 308 Brasilia", timeout=60)
            sug = adm.get(f"{amb.url}/admin/enderecos-sugestoes?texto=SQS 308 Brasilia", timeout=60)
            resultado[nome]["nominatim"] = {
                "geocodificar": [g.status_code, g.json() if g.ok else None],
                "sugestoes": [sug.status_code, sug.json() if sug.ok else None],
                "tempo_s": round(time.perf_counter() - t, 1),
            }
            print(f"  {nome}: {resultado[nome]}")
    finally:
        servidor_lento.shutdown()
        amb.derrubar_servidor()
        amb.env.pop("OSRM_BASE_URL")
        amb.env.pop("NOMINATIM_BASE_URL")
        amb.subir_servidor()
    return resultado


def backup_restauracao(amb):
    consulta = ("SELECT (SELECT count(*) FROM usuario)||'/'||(SELECT count(*) FROM hospital)||'/'||"
                "(SELECT count(*) FROM ocorrencia)||'/'||(SELECT count(*) FROM paciente)||'/'||"
                "(SELECT count(*) FROM mensagem)||'/'||(SELECT count(*) FROM auditoria)")
    _, antes = amb.psql(consulta)
    t = time.perf_counter()
    dump = subprocess.run(["docker", "exec", amb.container, "pg_dump", "-U", "postgres", "-Fc", "-f",
                           "/tmp/orbis.dump", "orbis_nf"], capture_output=True, text=True)
    t_dump = round(time.perf_counter() - t, 2)
    _, tamanho = subprocess.getstatusoutput(f"docker exec {amb.container} du -h /tmp/orbis.dump")
    amb.derrubar_servidor()
    subprocess.run(["docker", "exec", amb.container, "dropdb", "-U", "postgres", "orbis_nf"], check=True)
    subprocess.run(["docker", "exec", amb.container, "createdb", "-U", "postgres", "orbis_nf"], check=True)
    t = time.perf_counter()
    rest = subprocess.run(["docker", "exec", amb.container, "pg_restore", "-U", "postgres", "-d", "orbis_nf",
                           "/tmp/orbis.dump"], capture_output=True, text=True)
    t_rest = round(time.perf_counter() - t, 2)
    _, depois = amb.psql(consulta)
    amb.subir_servidor()
    login_ok = amb.sessao(HOSPITAL).get(amb.url + "/dashboard").status_code == 200
    r = {"contagens_antes(usu/hosp/oc/pac/msg/aud)": antes, "contagens_depois": depois,
         "iguais": antes == depois, "dump_ok": dump.returncode == 0, "restore_ok": rest.returncode == 0,
         "tempo_dump_s": t_dump, "tempo_restore_s": t_rest, "tamanho_dump": tamanho.split()[0],
         "sistema_funciona_apos_restaurar": login_ok}
    print(f"  backup/restauração: {r}")
    return r


def main():
    with Ambiente(porta_db=55994, porta_app=5595, nome="orbis_nf_rec") as amb:
        _, livres = amb.psql(
            "SELECT u.email FROM usuario u JOIN socorrista s ON s.usuario_id=u.id WHERE u.ativo AND NOT EXISTS "
            "(SELECT 1 FROM ocorrencia o WHERE o.socorrista_id=s.id AND o.status<>'finalizada') LIMIT 2")
        print("== 1. Queda do servidor no meio do trajeto ==")
        r1 = queda_no_trajeto(amb)
        print("== 2. Banco reiniciado / desligado ==")
        r2 = queda_do_banco(amb)
        print("== 3/4. OSRM e Nominatim fora do ar ==")
        r3 = servicos_externos(amb, livres.splitlines())
        print("== 5. Backup e restauração ==")
        r5 = backup_restauracao(amb)
        salvar_resultado("recuperacao", {"queda_trajeto": r1, "banco": r2, "servicos_externos": r3,
                                         "backup_restauracao": r5})


if __name__ == "__main__":
    main()
