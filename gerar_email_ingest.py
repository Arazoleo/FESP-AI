#!/usr/bin/env python3
"""
Ingestor rerodável dos COMUNICADOS INSTITUCIONAIS da UNIFESP (email → RAG).

Lê os avisos em massa enviados às listas de alunos (read-only), grava um .md por
comunicado em markdown_comunicados/ e pede ao backend para reindexar. NUNCA lê
email privado, NUNCA envia/responde. Ver src/email_ingest.py para o detalhe do
filtro e da privacidade.

Pensado para rodar na mão ou pelo LaunchAgent com.fespai.email a cada ~30 min.

Uso:
    python3 gerar_email_ingest.py            # ingere novos e dispara reindex
    python3 gerar_email_ingest.py --dry-run  # mostra o que pegaria, sem gravar
    python3 gerar_email_ingest.py --no-reindex
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.email_ingest import ingerir  # noqa: E402

REINDEX_URL = "http://localhost:8000/reindex"


def _reindex() -> None:
    """Pede ao backend para reindexar (sync incremental). Falha soft."""
    try:
        import requests
        r = requests.post(REINDEX_URL, timeout=120)
        if r.ok:
            print(f"[reindex] ok: {r.json()}")
        else:
            print(f"[reindex] HTTP {r.status_code}")
    except Exception as e:
        print(f"[reindex] não foi possível avisar o backend ({e}). "
              "Os .md serão indexados no próximo restart do backend.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingestão de comunicados institucionais (email → RAG).")
    ap.add_argument("--dry-run", action="store_true", help="não grava nem reindexa")
    ap.add_argument("--no-reindex", action="store_true", help="grava mas não avisa o backend")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    resumo = ingerir(dry_run=args.dry_run)
    print(
        f"Comunicados: novos={resumo['novos']} pulados={resumo['pulados']} "
        f"ignorados_privado={resumo['ignorados_privado']}"
    )
    for nome in resumo["arquivos"]:
        print(f"  + {nome}")

    if resumo["novos"] and not args.dry_run and not args.no_reindex:
        _reindex()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
