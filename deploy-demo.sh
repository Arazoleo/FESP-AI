#!/usr/bin/env bash
# deploy-demo.sh — sobe a demo pública do FESP-AI via Cloudflare Quick Tunnel.
#
# 1. Sobe backend + frontend via docker-compose
# 2. Espera o backend ficar saudável (rag_ready=true)
# 3. Abre um Quick Tunnel (grátis, sem conta) apontando para o frontend :3000
#    — a API é servida pela MESMA origem via rewrites do next.config.js,
#    então um único túnel cobre tudo (chat, planner, etc).
#
# Uso: ./deploy-demo.sh
# Para derrubar: Ctrl+C (túnel) e `docker-compose down` se quiser parar tudo.

set -euo pipefail
cd "$(dirname "$0")"

TUNNEL_LOG="/tmp/tunnel.log"

echo "==> Subindo containers (docker-compose up -d)..."
docker-compose up -d

echo "==> Aguardando backend ficar saudável (rag_ready=true)..."
for i in $(seq 1 120); do
  if curl -sf -m 5 http://localhost:8000/health 2>/dev/null | grep -q '"rag_ready":true'; then
    echo "    Backend OK: $(curl -s -m 5 http://localhost:8000/health)"
    break
  fi
  if [ "$i" -eq 120 ]; then
    echo "ERRO: backend não ficou saudável em 10 min. Veja: docker logs fesp-ai-backend" >&2
    exit 1
  fi
  sleep 5
done

echo "==> Verificando frontend em http://localhost:3000..."
for i in $(seq 1 30); do
  curl -sf -o /dev/null -m 5 http://localhost:3000 && break
  [ "$i" -eq 30 ] && { echo "ERRO: frontend não respondeu." >&2; exit 1; }
  sleep 2
done
echo "    Frontend OK."

# Domínio FIXO gratuito do ngrok (nunca muda entre restarts). Requer
# `ngrok config add-authtoken <token>` feito uma vez. Fallback: cloudflared
# (URL aleatória) quando o ngrok não está instalado/configurado.
NGROK_DOMAIN="${NGROK_DOMAIN:-proclaim-exemplary-path.ngrok-free.dev}"

: > "$TUNNEL_LOG"
if command -v ngrok >/dev/null && ngrok config check >/dev/null 2>&1; then
  echo "==> Abrindo ngrok no domínio fixo $NGROK_DOMAIN..."
  ngrok http --domain="$NGROK_DOMAIN" 3000 --log=stdout >"$TUNNEL_LOG" 2>&1 &
  TUNNEL_PID=$!
  URL="https://$NGROK_DOMAIN"
else
  echo "==> ngrok não configurado — usando Cloudflare Quick Tunnel (URL muda a cada execução)..."
  # --protocol http2: redes que bloqueiam UDP/QUIC (porta 7844) derrubam o túnel
  cloudflared tunnel --protocol http2 --url http://localhost:3000 >"$TUNNEL_LOG" 2>&1 &
  TUNNEL_PID=$!
  URL=""
  for i in $(seq 1 30); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)
    [ -n "$URL" ] && break
    sleep 2
  done
fi
trap 'kill $TUNNEL_PID 2>/dev/null || true' EXIT INT TERM

if [ -z "$URL" ]; then
  echo "ERRO: não consegui obter a URL do túnel. Log: $TUNNEL_LOG" >&2
  exit 1
fi

echo "==> Verificando a URL pública..."
for i in $(seq 1 15); do
  curl -sf -m 10 "$URL/api/health" >/dev/null && break
  [ "$i" -eq 15 ] && echo "AVISO: $URL ainda não respondeu ao health — verifique $TUNNEL_LOG" >&2
  sleep 2
done

echo ""
echo "=================================================================="
echo ""
echo "   DEMO PÚBLICA NO AR:"
echo ""
echo "   >>>   $URL   <<<"
echo ""
echo "=================================================================="
echo ""
echo "Log do túnel: $TUNNEL_LOG (Ctrl+C encerra o túnel; containers seguem no ar)"
echo ""

# Mantém o túnel em primeiro plano
wait $TUNNEL_PID
