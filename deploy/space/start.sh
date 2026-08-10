#!/usr/bin/env bash
set -e

ollama serve &

i=0
until curl -sf http://127.0.0.1:11434 >/dev/null; do
  i=$((i+1))
  if [ "$i" -gt 60 ]; then
    echo "ollama nao subiu a tempo"
    exit 1
  fi
  sleep 1
done

exec python start_api.py
