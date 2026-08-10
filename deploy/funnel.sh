#!/usr/bin/env bash
set -euo pipefail

TS="$(command -v tailscale || true)"
if [ -z "$TS" ] && [ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]; then
  TS="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
fi
if [ -z "$TS" ]; then
  echo "Tailscale nao encontrado. Instale com: brew install --cask tailscale"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

docker compose up -d backend

"$TS" funnel --bg 8000

echo ""
echo "Funnel ativo. URL publica do backend:"
"$TS" funnel status | grep -o 'https://[^ ]*\.ts\.net[^ ]*' | head -1
