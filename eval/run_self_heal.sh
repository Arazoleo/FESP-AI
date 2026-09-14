#!/usr/bin/env bash
# Fase 4 — tick agendado do loop de auto-correção.
#
# SEGURO por padrão: roda a triagem + o orquestrador (surface tickets/work
# orders/curadoria) e registra. NÃO corrige código sozinho.
#
# Autonomia opcional (opt-in): com FIXER_AUTO=1 e o `claude` CLI instalado,
# dispara o fixer headless por work order (diagnostica→corrige→verifica→abre PR).
# O merge continua sendo do HUMANO — nunca faz merge.
#
# Instale como launchd (ver eval/com.fespai.selfheal.plist) ou cron.
set -euo pipefail

REPO="${FESPAI_REPO:-/Users/arazoleonardo/fespai}"
CONTAINER="${FESPAI_CONTAINER:-fesp-ai-backend}"
LOG="${REPO}/chroma_db_unifesp/self_heal.log"
cd "$REPO"

{
  echo "==== self-heal tick $(date '+%Y-%m-%d %H:%M:%S') ===="
  # triagem precisa dos embeddings/KG → roda no container; escreve os tickets
  # no volume compartilhado chroma_db_unifesp/.
  docker exec "$CONTAINER" bash -lc \
    "cd /app && python eval/triage_misses.py" \
    2>&1 | grep -vE "NotOpenSSL|warnings.warn|httpx:" || true
  # orquestração é I/O puro dos JSONL (sem embeddings) → roda no host, lê os
  # tickets que a triagem gravou no volume compartilhado.
  python3 eval/self_heal.py 2>&1 || true

  if [ "${FIXER_AUTO:-0}" = "1" ] && command -v claude >/dev/null 2>&1; then
    echo "-- fixer autônomo (headless) na work order de maior impacto --"
    # processa 1 work order por tick; o fixer abre PR (humano faz o merge)
    claude -p "Rode o runbook do fixer (self-heal Fase 3) na work order de \
maior frequência em chroma_db_unifesp/self_heal_workorders.jsonl que ainda \
não tenha PR: diagnostique, corrija no estilo da casa (grounding+semântica, \
sem regex, cite fonte), rode eval/gen_prod_tests.py + a suíte + eval/fixer_pr.py \
--pr, e pare. Se for gap de DADO, apenas anexe à data_curation_queue.jsonl." \
      2>&1 | tail -20 || echo "(fixer headless falhou; tickets seguem na fila)"
  else
    echo "-- modo seguro: só triagem/orquestração (FIXER_AUTO!=1) --"
  fi
  echo "==== fim do tick ===="
} >> "$LOG" 2>&1

echo "self-heal tick concluído; log em $LOG"
