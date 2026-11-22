#!/usr/bin/env bash
# Abre o app OrbisHealth no Expo Go a partir de QUALQUER rede (5G do celular,
# Wi-Fi diferente do computador...). Faz três coisas:
#
#   1. sobe o backend Flask na porta 5000 (ou usa o que já estiver rodando);
#   2. cria um túnel ngrok para ele (endereço público https://...ngrok...);
#   3. inicia o Expo com --tunnel, já avisando o app do endereço do backend.
#
# Requisitos: ngrok com authtoken configurado (ngrok config add-authtoken ...).
# Uso:        ./iniciar-celular.sh        (Ctrl+C encerra tudo que ele abriu)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")" && pwd)"
PORTA="${PORTA:-5000}"
LOGS="${TMPDIR:-/tmp}/orbis-celular"
mkdir -p "$LOGS"
PIDS=()

encerrar() {
  echo
  echo "Encerrando o que este script iniciou..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
}
trap encerrar EXIT INT TERM

porta_aberta() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# ------------------------------------------------------------------ backend
if porta_aberta "$PORTA"; then
  echo "✔ Backend já está rodando na porta $PORTA (vou usar esse)."
else
  echo "▶ Subindo o backend (log em $LOGS/backend.log)..."
  (
    cd "$RAIZ/backend"
    # shellcheck disable=SC1091
    source venv/bin/activate
    exec python run.py
  ) >"$LOGS/backend.log" 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 40); do porta_aberta "$PORTA" && break; sleep 0.5; done
  porta_aberta "$PORTA" || { echo "✖ O backend não subiu. Veja $LOGS/backend.log"; exit 1; }
  echo "✔ Backend no ar."
fi

# ------------------------------------------------------- túnel do backend
command -v ngrok >/dev/null || { echo "✖ ngrok não encontrado. Instale em https://ngrok.com/download"; exit 1; }

url_do_tunel() {
  # API local do ngrok (porta 4040): procura o túnel https que aponta para a porta do backend
  curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import json, sys
try:
    dados = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for t in dados.get('tunnels', []):
    if t.get('public_url', '').startswith('https') and t.get('config', {}).get('addr', '').endswith(':$PORTA'):
        print(t['public_url']); break
"
}

API_URL="$(url_do_tunel || true)"
if [ -n "$API_URL" ]; then
  echo "✔ Túnel do backend já existia: $API_URL"
else
  echo "▶ Abrindo túnel ngrok para o backend (log em $LOGS/ngrok.log)..."
  ngrok http "$PORTA" --log=stdout >"$LOGS/ngrok.log" 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 30); do
    API_URL="$(url_do_tunel || true)"
    [ -n "$API_URL" ] && break
    sleep 0.5
  done
  [ -n "$API_URL" ] || { echo "✖ O ngrok não abriu o túnel. Veja $LOGS/ngrok.log"; tail -5 "$LOGS/ngrok.log"; exit 1; }
  echo "✔ Backend público em: $API_URL"
fi

# confere de ponta a ponta: a API responde pelo túnel?
if curl -s -H "ngrok-skip-browser-warning: 1" "$API_URL/api/v1/eu" | grep -q "erro"; then
  echo "✔ API respondendo pelo túnel."
else
  echo "⚠ A API não respondeu pelo túnel ainda; continuo mesmo assim."
fi

# --------------------------------------------------------------- Expo Go
echo
echo "▶ Iniciando o Expo com túnel. Quando aparecer o QR code:"
echo "    Android: abra o Expo Go e toque em \"Scan QR code\""
echo "    iPhone:  aponte a câmera para o QR code"
echo
# porta livre para o Metro (se a 8081 já estiver em uso, usa a próxima,
# em vez de parar para perguntar)
PORTA_EXPO=8081
while porta_aberta "$PORTA_EXPO"; do PORTA_EXPO=$((PORTA_EXPO + 1)); done
[ "$PORTA_EXPO" != 8081 ] && echo "  (a porta 8081 está ocupada por outro programa; usando $PORTA_EXPO)"

cd "$RAIZ/mobile"
EXPO_PUBLIC_API_URL="$API_URL" npx expo start --tunnel --clear --port "$PORTA_EXPO"
