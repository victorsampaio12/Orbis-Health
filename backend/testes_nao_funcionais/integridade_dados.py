"""
7.2.1 Integridade de dados e banco de dados.

1. Migrations: banco vazio -> upgrade head -> downgrade base -> upgrade head,
   e `flask db check` (os models batem com as migrations?).
2. Restrições: tenta gravar direto no PostgreSQL (sem passar pela aplicação)
   dados que violam unicidade, chave estrangeira, NOT NULL e enum.
3. Exclusão em cascata: apagar uma ocorrência leva pacientes, anexos e
   mensagens junto.
4. Consistência dos dados de demonstração: órfãos, status x datas,
   prioridade x sinais vitais (RN-010), lotação x capacidade (RN-006),
   anexos x arquivos em disco.

Uso:  python testes_nao_funcionais/integridade_dados.py
"""
import os
import subprocess
import sys

from ambiente import BACKEND_DIR, Ambiente, salvar_resultado

RESTRICOES = [
    ("e-mail de usuário duplicado (unique)",
     "CREATE TEMP TABLE copia AS SELECT * FROM usuario LIMIT 1; "
     "UPDATE copia SET id = id + 100000; INSERT INTO usuario SELECT * FROM copia"),
    ("dois hospitais para o mesmo usuário (RN-002, unique)",
     "INSERT INTO hospital (nome,endereco,tem_heliponto,tem_garagem,ativo,usuario_id) "
     "SELECT 'x','y',false,true,true,usuario_id FROM hospital LIMIT 1"),
    ("matrícula de socorrista duplicada (unique)",
     "INSERT INTO socorrista (usuario_id,matricula) "
     "SELECT (SELECT max(id) FROM usuario), matricula FROM socorrista LIMIT 1"),
    ("ocorrência de socorrista inexistente (FK)",
     "INSERT INTO ocorrencia (socorrista_id,veiculo,status,local,criado_em,atualizado_em) "
     "VALUES (999999,'ambulancia','aberta','x',now(),now())"),
    ("ocorrência com hospital inexistente (FK)",
     "UPDATE ocorrencia SET hospital_id = 999999 WHERE id = (SELECT min(id) FROM ocorrencia)"),
    ("paciente sem nome (NOT NULL)",
     "INSERT INTO paciente (ocorrencia_id,nome,motivo_chamado,prioridade,estavel,agravamento_registrado,"
     "melhorando,parada_cardiorrespiratoria,criado_em,atualizado_em) "
     "SELECT id,NULL,'x','media',false,false,false,false,now(),now() FROM ocorrencia LIMIT 1"),
    ("status de ocorrência fora do enum",
     "UPDATE ocorrencia SET status = 'cancelada' WHERE id = (SELECT min(id) FROM ocorrencia)"),
    ("papel de usuário fora do enum (RN-001)",
     "UPDATE usuario SET papel = 'visitante' WHERE id = (SELECT min(id) FROM usuario)"),
    ("anexo de paciente inexistente (FK)",
     "INSERT INTO anexo_paciente (paciente_id,enviado_por_id,nome_original,arquivo,largura,altura,"
     "tamanho_bytes,criado_em) VALUES (999999,1,'a.jpg','x/y.jpg',1,1,1,now())"),
    ("mensagem de remetente inexistente (FK)",
     "INSERT INTO mensagem (ocorrencia_id,remetente_id,conteudo,enviado_em,lida) "
     "SELECT id,999999,'x',now(),false FROM ocorrencia LIMIT 1"),
]

CONSISTENCIA = [
    ("pacientes sem ocorrência", "SELECT count(*) FROM paciente p LEFT JOIN ocorrencia o ON o.id=p.ocorrencia_id WHERE o.id IS NULL"),
    ("ocorrências sem paciente", "SELECT count(*) FROM ocorrencia o WHERE NOT EXISTS (SELECT 1 FROM paciente p WHERE p.ocorrencia_id=o.id)"),
    ("em transporte/finalizada sem hospital", "SELECT count(*) FROM ocorrencia WHERE status<>'aberta' AND hospital_id IS NULL"),
    ("aberta com hospital", "SELECT count(*) FROM ocorrencia WHERE status='aberta' AND hospital_id IS NOT NULL"),
    ("finalizada sem data/desfecho", "SELECT count(*) FROM ocorrencia WHERE status='finalizada' AND (finalizado_em IS NULL OR desfecho IS NULL)"),
    ("finalizada sem chegada confirmada", "SELECT count(*) FROM ocorrencia WHERE status='finalizada' AND chegada_confirmada_em IS NULL"),
    ("finalizada com chat aberto (RN-022)", "SELECT count(*) FROM ocorrencia WHERE status='finalizada' AND chat_encerrado_em IS NULL"),
    ("datas fora de ordem (fim antes do início)", "SELECT count(*) FROM ocorrencia WHERE finalizado_em < criado_em"),
    ("helicóptero para hospital sem heliponto (RN-003)",
     "SELECT count(*) FROM ocorrencia o JOIN hospital h ON h.id=o.hospital_id WHERE o.veiculo='helicoptero' AND NOT h.tem_heliponto"),
    ("ambulância para hospital sem garagem (RN-003)",
     "SELECT count(*) FROM ocorrencia o JOIN hospital h ON h.id=o.hospital_id WHERE o.veiculo='ambulancia' AND NOT h.tem_garagem"),
    ("hospital acima da capacidade (RN-006)",
     "SELECT count(*) FROM (SELECT h.id FROM hospital h JOIN ocorrencia o ON o.hospital_id=h.id "
     "AND o.status IN ('aberta','em_transporte') WHERE h.capacidade_maxima IS NOT NULL "
     "GROUP BY h.id, h.capacidade_maxima HAVING count(*) > h.capacidade_maxima) x"),
    ("prioridade crítica ausente com sinal crítico (RN-010)",
     "SELECT count(*) FROM paciente WHERE prioridade<>'critica' AND (parada_cardiorrespiratoria "
     "OR glasgow < 8 OR saturacao_o2 < 90)"),
    ("prioridade crítica sem motivo (RN-010)",
     "SELECT count(*) FROM paciente WHERE prioridade='critica' AND NOT (parada_cardiorrespiratoria "
     "OR coalesce(glasgow,15) < 8 OR coalesce(saturacao_o2,100) < 90)"),
    ("usuário sem papel (RN-001)", "SELECT count(*) FROM usuario WHERE papel IS NULL"),
    ("usuário hospital sem hospital vinculado",
     "SELECT count(*) FROM usuario u WHERE papel='hospital' AND NOT EXISTS (SELECT 1 FROM hospital h WHERE h.usuario_id=u.id)"),
    ("usuário socorrista sem cadastro de socorrista",
     "SELECT count(*) FROM usuario u WHERE papel='socorrista' AND NOT EXISTS (SELECT 1 FROM socorrista s WHERE s.usuario_id=u.id)"),
    ("nenhum admin ativo (RN-020)", "SELECT CASE WHEN count(*)=0 THEN 1 ELSE 0 END FROM usuario WHERE papel='admin' AND ativo"),
    ("mensagem de quem não é da dupla (RN-016)",
     "SELECT count(*) FROM mensagem m JOIN ocorrencia o ON o.id=m.ocorrencia_id "
     "JOIN socorrista s ON s.id=o.socorrista_id LEFT JOIN hospital h ON h.id=o.hospital_id "
     "WHERE m.remetente_id <> s.usuario_id AND m.remetente_id IS DISTINCT FROM h.usuario_id"),
    ("cadastros sem registro de auditoria (RN-017)",
     "SELECT CASE WHEN (SELECT count(*) FROM auditoria) >= (SELECT count(*) FROM hospital) THEN 0 ELSE 1 END"),
]


def migrations(amb):
    passos = {}
    for nome, args in [("upgrade head (banco vazio)", ["db", "upgrade"]),
                       ("downgrade base", ["db", "downgrade", "base"]),
                       ("upgrade head de novo", ["db", "upgrade"])]:
        r = amb.flask(*args, check=False)
        passos[nome] = "ok" if r.returncode == 0 else (r.stderr[-400:] or r.stdout[-400:])
        print(f"  {nome}: {passos[nome]}")
    r = amb.flask("db", "check", check=False)
    saida = (r.stdout + r.stderr).strip().splitlines()
    passos["flask db check (models x migrations)"] = "ok" if r.returncode == 0 else saida[-3:]
    print(f"  db check: {passos['flask db check (models x migrations)']}")
    _, versao = amb.psql("SELECT version_num FROM alembic_version")
    passos["versao_final"] = versao
    return passos


def restricoes(amb):
    resultado = []
    for nome, sql in RESTRICOES:
        codigo, saida = amb.psql(sql)
        recusou = codigo != 0
        erro = next((l for l in saida.splitlines() if l.startswith("ERROR")), saida[:150])
        resultado.append({"caso": nome, "recusado_pelo_banco": recusou, "erro": erro if recusou else None})
        print(f"  {'OK ' if recusou else 'FALHA'} {nome}: {erro if recusou else 'ACEITO!'}")
    return resultado


def cascata(amb):
    """Duas políticas diferentes, ambas conferidas:
    - ocorrência -> paciente/mensagem: RESTRICT. O banco impede apagar uma
      ocorrência que tem prontuário (o sistema não oferece exclusão de
      ocorrência; um DELETE manual por engano não pode sumir com prontuário).
    - paciente -> anexo: CASCADE. Apagar o paciente leva as fotos junto."""
    _, oid = amb.psql("SELECT p.ocorrencia_id FROM paciente p JOIN anexo_paciente a ON a.paciente_id=p.id LIMIT 1")
    _, pid = amb.psql(f"SELECT p.id FROM paciente p JOIN anexo_paciente a ON a.paciente_id=p.id "
                      f"WHERE p.ocorrencia_id={oid} LIMIT 1")
    codigo, saida = amb.psql(f"DELETE FROM ocorrencia WHERE id={oid}")
    restrict = {
        "ocorrencia": oid,
        "delete_recusado": codigo != 0,
        "erro": next((l for l in saida.splitlines() if l.startswith("ERROR")), None),
        "ocorrencia_continua_no_banco": amb.psql(f"SELECT count(*) FROM ocorrencia WHERE id={oid}")[1] == "1",
    }
    print(f"  ocorrência com prontuário (RESTRICT): {restrict}")

    _, anexos_antes = amb.psql(f"SELECT count(*) FROM anexo_paciente WHERE paciente_id={pid}")
    codigo, saida = amb.psql(f"DELETE FROM paciente WHERE id={pid}")
    _, anexos_depois = amb.psql(f"SELECT count(*) FROM anexo_paciente WHERE paciente_id={pid}")
    cascade = {"paciente": pid, "delete": "ok" if codigo == 0 else saida,
               "anexos_antes": int(anexos_antes), "anexos_depois": int(anexos_depois)}
    print(f"  paciente -> anexos (CASCADE): {cascade}")
    return {"ocorrencia_restrict": restrict, "paciente_cascade": cascade}


def consistencia(amb):
    resultado = []
    for nome, sql in CONSISTENCIA:
        _, n = amb.psql(sql)
        resultado.append({"verificacao": nome, "ocorrencias_inconsistentes": int(n)})
        print(f"  {'OK ' if n == '0' else 'FALHA'} {nome}: {n}")
    # anexos x arquivos em disco
    _, linhas = amb.psql("SELECT arquivo FROM anexo_paciente")
    faltando = [a for a in linhas.splitlines() if a and not os.path.exists(os.path.join(amb.uploads, a))]
    resultado.append({"verificacao": "anexo no banco sem arquivo em disco",
                      "ocorrencias_inconsistentes": len(faltando)})
    print(f"  {'OK ' if not faltando else 'FALHA'} anexos sem arquivo: {len(faltando)} de {len(linhas.splitlines())}")
    return resultado


def main():
    amb = Ambiente(porta_db=55992, porta_app=5597, nome="orbis_nf_integ")
    try:
        amb.subir_banco()
        print("== Migrations ==")
        mig = migrations(amb)
        print("== Populando com os dados de demonstração ==")
        amb.python(
            "import bcrypt\nfrom app import create_app, db\nfrom app.models.usuario import PapelEnum, Usuario\n"
            "app = create_app()\nwith app.app_context():\n"
            "    db.session.add(Usuario(nome='Admin', email='admin@orbishealth.com', senha_hash=bcrypt.hashpw("
            "b'Admin@123', bcrypt.gensalt()).decode(), papel=PapelEnum.admin, ativo=True))\n    db.session.commit()\n")
        subprocess.run([sys.executable, "seed_demo.py"], cwd=BACKEND_DIR, env=amb.env,
                       check=True, capture_output=True)
        _, contagens = amb.psql(
            "SELECT (SELECT count(*) FROM usuario)||' usuários, '||(SELECT count(*) FROM hospital)||' hospitais, '||"
            "(SELECT count(*) FROM ocorrencia)||' ocorrências, '||(SELECT count(*) FROM paciente)||' pacientes, '||"
            "(SELECT count(*) FROM mensagem)||' mensagens, '||(SELECT count(*) FROM anexo_paciente)||' anexos'")
        print(f"  {contagens}")
        print("== Consistência ==")
        cons = consistencia(amb)
        print("== Restrições do banco ==")
        rest = restricoes(amb)
        print("== Exclusão em cascata ==")
        casc = cascata(amb)
        salvar_resultado("integridade_dados", {
            "base": contagens, "migrations": mig, "restricoes": rest, "cascata": casc, "consistencia": cons})
    finally:
        subprocess.run(["docker", "rm", "-f", amb.container], capture_output=True)


if __name__ == "__main__":
    main()
