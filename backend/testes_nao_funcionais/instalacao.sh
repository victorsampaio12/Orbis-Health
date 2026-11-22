#!/usr/bin/env bash
# 7.2.12 Instalação.
#
# Instala o OrbisHealth do zero numa máquina limpa (container Docker só com
# o Python oficial, sem nada do projeto) seguindo o README, contra um
# PostgreSQL também novo, e confere se o sistema sobe e responde.
# Repete com Python 3.12 (versão do projeto) e 3.14 (versão mais nova).
#
# Uso:  bash testes_nao_funcionais/instalacao.sh
set -u
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
SAIDA="$AQUI/resultados/instalacao"
mkdir -p "$SAIDA"
REDE=orbis_inst_rede
PG=orbis_inst_pg

# "clone" limpo: só o que está no Git (sem venv, .env, uploads, backups)
PACOTE="$(mktemp -d)/orbis_fonte.tar"
(cd "$RAIZ" && git ls-files -co --exclude-standard -z | tar --null -T - -cf "$PACOTE")

docker network create "$REDE" >/dev/null 2>&1
docker rm -f "$PG" >/dev/null 2>&1
docker run -d --name "$PG" --network "$REDE" -e POSTGRES_PASSWORD=inst -e POSTGRES_DB=orbis_health postgres:15 >/dev/null
until docker exec "$PG" pg_isready -U postgres >/dev/null 2>&1; do sleep 0.5; done; sleep 1

PASSOS='
set -e
t() { date +%s.%N; }
mkdir /app && tar -xf /fonte.tar -C /app && cd /app/backend
echo "== sistema: $(python --version), $(uname -m)"
T0=$(t)
python -m venv venv && . venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt 2>&1 | tail -5
T1=$(t); echo "== pip install: $(echo "$T1 - $T0" | bc 2>/dev/null || python -c "print(round($T1-$T0,1))") s"
cp .env.example .env
sed -i "s/^DB_HOST=.*/DB_HOST=orbis_inst_pg/; s/^DB_PASSWORD=.*/DB_PASSWORD=inst/; s/^SECRET_KEY=.*/SECRET_KEY=chave-de-instalacao/" .env
export FLASK_APP=run.py
flask db upgrade 2>&1 | tail -1
python seed.py
python seed_demo.py | tail -3
T2=$(t); echo "== banco pronto: $(python -c "print(round($T2-$T1,1))") s"
python run.py > /tmp/servidor.log 2>&1 &
python - <<PY
import time, urllib.request, http.cookiejar, urllib.parse
inicio = time.time()
while True:
    try:
        urllib.request.urlopen("http://127.0.0.1:5000/login", timeout=2); break
    except Exception:
        if time.time() - inicio > 30: raise SystemExit("servidor não subiu")
        time.sleep(0.3)
print(f"== servidor no ar em {time.time()-inicio:.1f} s")
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
dados = urllib.parse.urlencode({"email": "admin@orbishealth.com", "senha": "Admin@123"}).encode()
r = op.open("http://127.0.0.1:5000/login", dados)
print("== login do admin:", "OK" if "/dashboard" in r.url or "/admin" in r.url else "FALHOU " + r.url)
r = op.open("http://127.0.0.1:5000/admin/hospitais")
print("== tela de hospitais:", r.status, "-", r.read().decode().count("hospital-row") or "carregou")
PY
echo "== INSTALACAO_OK"
'

for VERSAO in 3.12 3.14; do
  LOG="$SAIDA/python-$VERSAO.log"
  echo "### Python $VERSAO (log em $LOG)"
  INICIO=$(date +%s)
  docker run --rm --network "$REDE" -v "$PACOTE:/fonte.tar:ro" "python:$VERSAO-slim" bash -c "$PASSOS" > "$LOG" 2>&1
  CODIGO=$?
  echo "    código de saída: $CODIGO, tempo total: $(( $(date +%s) - INICIO )) s"
  grep -E "^== |ERROR|error:|Error" "$LOG" | head -12 | sed 's/^/    /'
  # banco limpo para a próxima versão
  docker exec "$PG" psql -U postgres -q -c "DROP DATABASE orbis_health" -c "CREATE DATABASE orbis_health" postgres >/dev/null
done

docker rm -f "$PG" >/dev/null
docker network rm "$REDE" >/dev/null
rm -f "$PACOTE"
