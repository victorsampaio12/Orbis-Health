"""
7.2.8 Volume.

Mede as telas mais pesadas com a base de demonstração (~60 ocorrências) e
depois de inserir um ano de operação simulada: 20.000 ocorrências
finalizadas (metade no Hospital de Base), com paciente e 3 mensagens cada
(60.000 mensagens). Compara tempo de resposta e tamanho da resposta.

Uso:  python testes_nao_funcionais/volume.py
"""
import time

from ambiente import ADMIN_EMAIL, ADMIN_SENHA, Ambiente, salvar_resultado
from desempenho_carga_stress import HOSPITAL, descobrir_dados, medir_rota

N_OCORRENCIAS = 20000

GERAR_VOLUME = f"""
WITH hb AS (SELECT h.id FROM hospital h JOIN usuario u ON u.id=h.usuario_id WHERE u.email='{HOSPITAL}'),
hs AS (SELECT array_agg(id) a FROM hospital WHERE tem_garagem),
ss AS (SELECT array_agg(id) a FROM socorrista),
novas AS (
  INSERT INTO ocorrencia (socorrista_id, hospital_id, destino_latitude, destino_longitude, veiculo, status,
      tipo_rota, local, comentarios, latitude_atual, longitude_atual, distancia_estimada_km, tempo_estimado_min,
      chegada_confirmada_em, finalizado_em, desfecho, chat_encerrado_em, criado_em, atualizado_em)
  SELECT ss.a[1 + (g % array_length(ss.a,1))],
         CASE WHEN g % 2 = 0 THEN (SELECT id FROM hb) ELSE hs.a[1 + (g % array_length(hs.a,1))] END,
         -15.80, -47.88, 'ambulancia', 'finalizada', 'terrestre',
         'Volume ' || g || ' - Quadra ' || (g % 400) || ', Brasília - DF', 'Carga de volume',
         -15.80, -47.88, 5.0, 12.0,
         t + interval '20 min', t + interval '50 min', 'Atendido e liberado', t + interval '50 min', t, t
  FROM generate_series(1, {N_OCORRENCIAS}) g, hs, ss,
       LATERAL (SELECT now() - (g * interval '26 minutes') AS t) tt
  RETURNING id, socorrista_id, hospital_id, criado_em
),
pac AS (
  INSERT INTO paciente (ocorrencia_id, nome, motivo_chamado, prioridade, estavel, agravamento_registrado,
      melhorando, parada_cardiorrespiratoria, criado_em, atualizado_em)
  SELECT id, 'Paciente ' || id, 'Queda', 'media', true, false, false, false, criado_em, criado_em FROM novas
)
INSERT INTO mensagem (ocorrencia_id, remetente_id, conteudo, enviado_em, lida)
SELECT n.id, CASE WHEN k % 2 = 1 THEN s.usuario_id ELSE h.usuario_id END,
       'Mensagem ' || k || ' da ocorrência ' || n.id, n.criado_em + k * interval '3 min', true
FROM novas n JOIN socorrista s ON s.id = n.socorrista_id JOIN hospital h ON h.id = n.hospital_id,
     generate_series(1, 3) k;
ANALYZE;
"""


def rotas(oc):
    return {
        "hospital": ["/dashboard", "/emergencias/historico", "/emergencias/historico?pagina=1250",
                     "/emergencias/historico?busca=Quadra%20123", "/emergencias/historico?status=finalizada&por_pagina=24",
                     "/emergencias/historico/exportar", "/inbox/", f"/ocorrencias/{oc}"],
        "socorrista": ["/dashboard", "/inbox/", f"/ocorrencias/{oc}"],
        "admin": ["/admin/", "/admin/dashboard-dados", "/admin/hospitais", "/admin/socorristas"],
    }


def medir_tudo(amb, sessoes, oc, rotulo):
    resultado = {}
    for perfil, lista in rotas(oc).items():
        for rota in lista:
            m = medir_rota(sessoes[perfil], amb.url + rota, n=10)
            resultado[f"{perfil} {rota}"] = m
            print(f"  [{rotulo}] {perfil:10} {rota:58} p50={m['p50_ms']:>8} ms  {m['bytes']/1024:>8.1f} KB  {m['status']}")
    return resultado


def main():
    with Ambiente(porta_db=55993, porta_app=5596, nome="orbis_nf_vol") as amb:
        oc, soc_email, _ = descobrir_dados(amb)
        sessoes = {"hospital": amb.sessao(HOSPITAL), "socorrista": amb.sessao(soc_email),
                   "admin": amb.sessao(ADMIN_EMAIL, ADMIN_SENHA)}
        _, antes_n = amb.psql("SELECT count(*) FROM ocorrencia")
        print(f"== Base de demonstração ({antes_n} ocorrências) ==")
        base = medir_tudo(amb, sessoes, oc, "base")

        t = time.perf_counter()
        codigo, saida = amb.psql(GERAR_VOLUME)
        assert codigo == 0, saida
        carga_s = round(time.perf_counter() - t, 1)
        _, contagem = amb.psql("SELECT (SELECT count(*) FROM ocorrencia)||';'||(SELECT count(*) FROM paciente)||';'||"
                               "(SELECT count(*) FROM mensagem)||';'||pg_size_pretty(pg_database_size('orbis_nf'))")
        n_oc, n_pac, n_msg, tamanho = contagem.split(";")
        print(f"== Volume: {n_oc} ocorrências, {n_pac} pacientes, {n_msg} mensagens, banco {tamanho} "
              f"(inserido em {carga_s} s) ==")
        volume = medir_tudo(amb, sessoes, oc, "volume")

        salvar_resultado("volume", {
            "base": {"ocorrencias": int(antes_n), "medicoes": base},
            "volume": {"ocorrencias": int(n_oc), "pacientes": int(n_pac), "mensagens": int(n_msg),
                       "tamanho_banco": tamanho, "tempo_insercao_s": carga_s, "medicoes": volume},
        })


if __name__ == "__main__":
    main()
