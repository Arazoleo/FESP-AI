"""
Gerador de testes dirigidos por PRODUÇÃO (Fase 2 do loop de auto-correção).

Transforma os misses recorrentes (via triage_tickets.jsonl, senão o
misses_queue.jsonl bruto) em uma SUÍTE DE REGRESSÃO real: cada pergunta que
falhou em produção vira um caso que exige do backend uma resposta ATERRADA
(não-miss). É o "verificador movido a produção" — o portão que o fixer do loop
usa para confirmar que corrigiu, e que trava a regressão para sempre.

O oráculo de miss é o MESMO do runtime (workflow.second_chance.is_miss_response),
não uma lista de palavras.

Uso:
    python eval/gen_prod_tests.py --min 2   # gera test_prod_regressions.py
                                            # (perguntas com >= 2 ocorrências)
Rodar a suíte gerada (com o backend no ar):
    FESPAI_URL=http://localhost:8000 python test_prod_regressions.py
"""

import os
import sys
import json
import re
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.getenv("FESPAI_DATA_DIR", os.path.join(ROOT, "chroma_db_unifesp"))
TICKETS = os.path.join(DATA, "triage_tickets.jsonl")
MISSES = os.path.join(DATA, "misses_queue.jsonl")
OUT = os.path.join(ROOT, "test_prod_regressions.py")

_min = 2
if "--min" in sys.argv:
    try:
        _min = int(sys.argv[sys.argv.index("--min") + 1])
    except Exception:
        pass


def _load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower().strip(" ?.!,"))


def _casos():
    """(pergunta_representante, frequencia) das falhas recorrentes."""
    tickets = _load(TICKETS)
    if tickets:
        return [(t["representante"], t["frequencia"]) for t in tickets
                if t.get("frequencia", 0) >= _min]
    # fallback: agrega o misses_queue bruto
    c = collections.Counter(_norm(m.get("question", "")) for m in _load(MISSES))
    return [(q, n) for q, n in c.most_common() if n >= _min and q]


TEMPLATE = '''"""
AUTO-GERADO por eval/gen_prod_tests.py — NÃO editar à mão.

Suíte de regressão dirigida por PRODUÇÃO: cada caso é uma pergunta que falhou
(miss) em produção; o backend deve agora dar uma resposta ATERRADA (não-miss).
Requer o backend no ar (FESPAI_URL, default http://localhost:8000). O oráculo de
miss é o mesmo do runtime.
"""
import os, sys, json, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.workflow.second_chance import is_miss_response

BASE = os.getenv("FESPAI_URL", "http://localhost:8000")
GREEN, RED, RESET = "\\033[92m", "\\033[91m", "\\033[0m"
_passed = _failed = 0

# (pergunta, frequencia_em_producao)
CASOS = {casos!r}


def _perguntar(q):
    data = json.dumps({{"message": q, "conversation_id": f"prodreg-{{abs(hash(q))}}"}}).encode()
    req = urllib.request.Request(BASE + "/chat", data=data,
                                 headers={{"Content-Type": "application/json"}})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


for q, freq in CASOS:
    try:
        d = _perguntar(q)
        resp = d.get("response", "")
        ok = bool(resp) and not is_miss_response(resp)
    except Exception as e:
        ok, d = False, {{"active_agent": f"ERRO {{e}}"}}
    if ok:
        _passed += 1
        print(f"{{GREEN}}OK{{RESET}} [{{freq}}x] {{q[:52]}} -> {{d.get('active_agent')}}")
    else:
        _failed += 1
        print(f"{{RED}}XX [{{freq}}x] {{q[:52]}} -> {{d.get('active_agent')}}{{RESET}}")

print(f"\\n{{_passed}} passed, {{_failed}} failed "
      f"(regressões de produção)")
sys.exit(1 if _failed else 0)
'''


def main():
    casos = _casos()
    if not casos:
        print("sem casos recorrentes (rode a triagem antes)."); return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(casos=casos))
    print(f"gerado {OUT} com {len(casos)} casos (>= {_min}x em produção)")


if __name__ == "__main__":
    main()
