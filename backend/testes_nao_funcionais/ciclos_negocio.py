"""
7.2.3 Ciclos de negócio.

1. Ciclo completo de atendimento, 3 socorristas ao mesmo tempo, todos para
   o mesmo hospital, só por HTTP (como o navegador faria):
   abrir ocorrência -> prontuário -> escolher hospital -> gerar rota (OSRM)
   -> iniciar trajeto -> esperar a viatura chegar -> confirmar chegada ->
   finalizar -> relatório -> chat encerrado -> histórico e CSV do hospital.
2. Ciclo de lotação (RN-006): o hospital passa por disponível -> crítico
   -> lotado conforme recebe as emergências e volta a disponível quando
   elas são finalizadas.
3. Virada do dia e do mês no fuso de Brasília: uma ocorrência às 23:30 de
   31/10 (02:30 UTC de 01/11) tem que aparecer no filtro de 31/10, no mês
   de outubro e no CSV com a hora local; "finalizadas hoje" do painel do
   admin conta pelo dia de Brasília.

Uso:  python testes_nao_funcionais/ciclos_negocio.py
"""
import re
import threading
import time

from ambiente import ADMIN_EMAIL, ADMIN_SENHA, Ambiente, salvar_resultado

N_CICLOS = 3


def status_no_painel(amb, sessao_soc, oid_aberta, nome_hospital):
    html = sessao_soc.get(f"{amb.url}/ocorrencias/{oid_aberta}/hospitais").text
    i = html.find(f"<h2>{nome_hospital}</h2>")
    trecho = html[i:i + 400]
    m = re.search(r"status-(disponivel|critico|lotado)", trecho)
    leitos = re.search(r"<strong>(\d+) de (\d+) leitos", html[i:i + 900])
    return (m.group(1) if m else None), (leitos.groups() if leitos else None)


def um_ciclo(amb, email, hid, registro, trava, barreira):
    etapas, t0 = {}, time.perf_counter()

    def marca(nome):
        etapas[nome] = round(time.perf_counter() - t0, 1)

    s = amb.sessao(email)
    s.post(amb.url + "/ocorrencias/novo", data={"local": f"Ciclo {email} - Esplanada dos Ministérios",
                                                "veiculo": "ambulancia", "latitude": "-15.7990",
                                                "longitude": "-47.8640"})
    _, oid = amb.psql("SELECT max(o.id) FROM ocorrencia o JOIN socorrista s ON s.id=o.socorrista_id "
                      f"JOIN usuario u ON u.id=s.usuario_id WHERE u.email='{email}'")
    marca("aberta")
    s.post(f"{amb.url}/ocorrencias/{oid}/pacientes/novo",
           data={"nome": f"Paciente do ciclo {oid}", "motivo_chamado": "Dor torácica", "saturacao_o2": "93",
                 "frequencia_cardiaca": "110", "glasgow": "15"})
    marca("prontuario")
    barreira.wait()  # os três escolhem o hospital ao mesmo tempo
    s.post(f"{amb.url}/ocorrencias/{oid}/selecionar-hospital", data={"hospital_id": hid})
    marca("hospital_escolhido")
    barreira.wait()
    with trava:
        registro.setdefault("_apos_selecao", []).append(oid)
    barreira.wait()  # o principal observa a lotação aqui
    barreira.wait()
    s.post(f"{amb.url}/ocorrencias/{oid}/gerar-rota")
    _, rota = amb.psql(f"SELECT coalesce(tipo_rota::text,'') || '|' || (rota_geometria IS NOT NULL) "
                       f"FROM ocorrencia WHERE id={oid}")
    marca("rota_gerada")
    amb.psql(f"UPDATE ocorrencia SET tempo_estimado_min = 0.5 WHERE id={oid}")  # trajeto simulado de 30 s
    r = s.post(f"{amb.url}/ocorrencias/{oid}/iniciar-trajeto")
    marca("trajeto_iniciado")
    chegou = False
    for _ in range(40):
        time.sleep(2)
        s.get(f"{amb.url}/ocorrencias/{oid}")
        s.post(f"{amb.url}/ocorrencias/{oid}/marcar-chegada")
        _, c = amb.psql(f"SELECT chegada_confirmada_em IS NOT NULL FROM ocorrencia WHERE id={oid}")
        if c == "t":
            chegou = True
            break
    marca("chegada_confirmada")
    s.post(f"{amb.url}/ocorrencias/{oid}/finalizar", data={"desfecho": "Paciente estabilizado e internado."})
    marca("finalizada")
    _, final = amb.psql(f"SELECT status||'|'||(chat_encerrado_em IS NOT NULL)||'|'||(finalizado_em IS NOT NULL) "
                        f"FROM ocorrencia WHERE id={oid}")
    with trava:
        registro[oid] = {"socorrista": email, "rota": rota, "iniciar_trajeto": r.status_code,
                         "chegou": chegou, "final(status|chat_encerrado|data)": final, "etapas_s": etapas}


def ciclo_completo_e_lotacao(amb):
    _, livres = amb.psql(
        "SELECT string_agg(email, ',') FROM (SELECT u.email FROM usuario u JOIN socorrista s ON s.usuario_id=u.id "
        "WHERE u.ativo AND NOT EXISTS (SELECT 1 FROM ocorrencia o WHERE o.socorrista_id=s.id "
        f"AND o.status<>'finalizada') ORDER BY u.id LIMIT {N_CICLOS + 1}) x")
    livres = livres.split(",")
    observador, ciclistas = livres[0], livres[1:]

    # hospital do ciclo: Hospital Regional do Guará, capacidade = ativas + 3
    _, linha = amb.psql(
        "SELECT h.id||'|'||h.nome||'|'||u.email||'|'||(SELECT count(*) FROM ocorrencia o WHERE o.hospital_id=h.id "
        "AND o.status<>'finalizada') FROM hospital h JOIN usuario u ON u.id=h.usuario_id "
        "WHERE h.tem_garagem AND h.ativo AND h.nome ILIKE '%Guará%' LIMIT 1")
    hid, nome, hosp_email, ativas = linha.split("|")
    capacidade = int(ativas) + N_CICLOS
    amb.psql(f"UPDATE hospital SET capacidade_maxima={capacidade} WHERE id={hid}")

    # observador: uma ocorrência aberta para enxergar a lista de hospitais
    obs = amb.sessao(observador)
    obs.post(amb.url + "/ocorrencias/novo", data={"local": "Observador - Setor Comercial Sul",
                                                  "veiculo": "ambulancia", "latitude": "-15.80",
                                                  "longitude": "-47.89"})
    _, oid_obs = amb.psql("SELECT max(o.id) FROM ocorrencia o JOIN socorrista s ON s.id=o.socorrista_id "
                          f"JOIN usuario u ON u.id=s.usuario_id WHERE u.email='{observador}'")
    adm = amb.sessao(ADMIN_EMAIL, ADMIN_SENHA)
    finalizadas_hoje_antes = adm.get(amb.url + "/admin/dashboard-dados").json()["finalizadas_hoje"]

    lotacao = [("antes", *status_no_painel(amb, obs, oid_obs, nome))]
    registro, trava = {}, threading.Lock()
    barreira = threading.Barrier(N_CICLOS + 1)
    threads = [threading.Thread(target=um_ciclo, args=(amb, e, hid, registro, trava, barreira))
               for e in ciclistas]
    [t.start() for t in threads]
    barreira.wait()  # seleção
    barreira.wait()
    barreira.wait()
    lotacao.append(("depois de 3 seleções simultâneas", *status_no_painel(amb, obs, oid_obs, nome)))
    # um 4º socorrista (o observador) tenta escolher o hospital lotado
    r = obs.post(f"{amb.url}/ocorrencias/{oid_obs}/selecionar-hospital", data={"hospital_id": hid})
    _, quarto = amb.psql(f"SELECT coalesce(hospital_id::text,'nenhum') FROM ocorrencia WHERE id={oid_obs}")
    barreira.wait()
    [t.join() for t in threads]
    lotacao.append(("depois das 3 finalizações", *status_no_painel(amb, obs, oid_obs, nome)))

    hosp = amb.sessao(hosp_email)
    historico = hosp.get(amb.url + "/emergencias/historico?status=finalizada&por_pagina=24").text
    csv_texto = hosp.get(amb.url + "/emergencias/historico/exportar").text
    ids = [k for k in registro if not str(k).startswith("_")]
    relatorios = {oid: hosp.get(f"{amb.url}/ocorrencias/{oid}/relatorio").status_code for oid in ids}
    finalizadas_hoje_depois = adm.get(amb.url + "/admin/dashboard-dados").json()["finalizadas_hoje"]
    resultado = {
        "hospital": nome, "capacidade": capacidade,
        "ciclos": {k: v for k, v in registro.items() if not str(k).startswith("_")},
        "lotacao": [{"momento": m, "status": s, "leitos(ocupados,total)": l} for m, s, l in lotacao],
        "quarto_socorrista_no_hospital_lotado": {"http": r.status_code, "hospital_vinculado": quarto},
        "historico_mostra_as_3": all(f"EMG-{int(o):04d}" in historico for o in ids),
        "csv_tem_as_3": all(f"EMG-{int(o):04d}" in csv_texto for o in ids),
        "relatorio_http": relatorios,
        "finalizadas_hoje_admin": [finalizadas_hoje_antes, finalizadas_hoje_depois],
    }
    for k, v in resultado.items():
        print(f"  {k}: {v}")
    return resultado


def virada_de_dia(amb):
    """Ocorrências criadas em horários de borda (UTC no banco) e conferidas
    pelos filtros do histórico, que trabalham no dia de Brasília."""
    _, hid_email = amb.psql("SELECT h.id||'|'||u.email FROM hospital h JOIN usuario u ON u.id=h.usuario_id "
                            "WHERE h.nome ILIKE '%Base%' LIMIT 1")
    hid, email = hid_email.split("|")
    _, sid = amb.psql("SELECT id FROM socorrista ORDER BY id LIMIT 1")
    casos = {
        "31/10 23:30 em Brasília (01/11 02:30 UTC)": "2026-11-01 02:30:00",
        "01/11 00:30 em Brasília (01/11 03:30 UTC)": "2026-11-01 03:30:00",
        "30/09 22:00 em Brasília (01/10 01:00 UTC)": "2026-10-01 01:00:00",
    }
    ids = {}
    for nome, utc in casos.items():
        _, oid = amb.psql(
            "INSERT INTO ocorrencia (socorrista_id,hospital_id,destino_latitude,destino_longitude,veiculo,status,"
            "tipo_rota,local,criado_em,atualizado_em,chegada_confirmada_em,finalizado_em,desfecho,chat_encerrado_em) "
            f"VALUES ({sid},{hid},-15.8,-47.88,'ambulancia','finalizada','terrestre','Borda {nome}',"
            f"'{utc}','{utc}','{utc}'::timestamp + interval '20 min','{utc}'::timestamp + interval '40 min','ok',"
            f"'{utc}'::timestamp + interval '40 min') RETURNING id")
        oid = oid.splitlines()[0]
        amb.psql(f"INSERT INTO paciente (ocorrencia_id,nome,motivo_chamado,prioridade,estavel,agravamento_registrado,"
                 f"melhorando,parada_cardiorrespiratoria,criado_em,atualizado_em) VALUES ({oid},'P','x','media',"
                 f"true,false,false,false,now(),now())")
        ids[nome] = f"EMG-{int(oid):04d}"
    s = amb.sessao(email)

    def codigos(query):
        html = s.get(f"{amb.url}/emergencias/historico?{query}&por_pagina=24").text
        return {n for n, c in ids.items() if c in html}

    filtros = {
        "dia 31/10": ("data_inicio=2026-10-31&data_fim=2026-10-31", {"31/10 23:30 em Brasília (01/11 02:30 UTC)"}),
        "dia 01/11": ("data_inicio=2026-11-01&data_fim=2026-11-01", {"01/11 00:30 em Brasília (01/11 03:30 UTC)"}),
        "mês de outubro": ("data_inicio=2026-10-01&data_fim=2026-10-31", {"31/10 23:30 em Brasília (01/11 02:30 UTC)"}),
        "mês de setembro": ("data_inicio=2026-09-01&data_fim=2026-09-30", {"30/09 22:00 em Brasília (01/10 01:00 UTC)"}),
    }
    resultado = {}
    for nome, (q, esperado) in filtros.items():
        obtido = codigos(f"busca=Borda&{q}")
        resultado[nome] = {"esperado": sorted(esperado), "obtido": sorted(obtido), "ok": obtido == esperado}
        print(f"  {'OK ' if obtido == esperado else 'FALHA'} {nome}: {sorted(obtido)}")
    csv_texto = s.get(f"{amb.url}/emergencias/historico/exportar?busca=Borda").text
    linha = next(l for l in csv_texto.splitlines() if "31/10 23:30" in l and "EMG" in l)
    resultado["csv_hora_local"] = {"linha": linha, "ok": ";31/10/2026 23:30;" in linha}
    print(f"  {'OK ' if resultado['csv_hora_local']['ok'] else 'FALHA'} CSV com hora de Brasília: {linha}")
    return resultado


def main():
    with Ambiente(porta_db=55996, porta_app=5593, nome="orbis_nf_ciclo") as amb:
        print("== Ciclo completo x3 e lotação ==")
        r1 = ciclo_completo_e_lotacao(amb)
        print("== Virada de dia e de mês ==")
        r2 = virada_de_dia(amb)
        salvar_resultado("ciclos_negocio", {"ciclo_e_lotacao": r1, "virada_de_dia": r2})


if __name__ == "__main__":
    main()
