"""
Quantas chamadas e tokens de LLM uma pergunta custa (para dimensionar a cota do Groq).

Amostra perguntas reais de chroma_db_unifesp/interactions.jsonl, estratificadas
por agente, manda cada uma ao /chat do backend e lê a diferença em /llm_usage.
Só mede com LLM_PROVIDER=groq (é o GroqLLM que conta).

Uso: python eval/medir_chamadas_llm.py --n 30 [--api http://localhost:8000]
"""

import argparse
import json
import random
import statistics
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _get(api, rota):
    with urllib.request.urlopen(f"{api}{rota}", timeout=30) as r:
        return json.loads(r.read())


def _post(api, rota, corpo):
    req = urllib.request.Request(f"{api}{rota}", json.dumps(corpo).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def amostra(n, semente=11):
    por_agente = defaultdict(set)
    for linha in open(ROOT / "chroma_db_unifesp/interactions.jsonl", encoding="utf-8"):
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if d.get("question"):
            por_agente[d.get("agent") or "?"].add(d["question"].strip())
    rnd = random.Random(semente)
    agentes = sorted(por_agente)
    saida = []
    while len(saida) < n and any(por_agente.values()):
        for a in agentes:
            if por_agente[a] and len(saida) < n:
                q = rnd.choice(sorted(por_agente[a]))
                por_agente[a].discard(q)
                saida.append((a, q))
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--api", default="http://localhost:8000")
    a = ap.parse_args()

    if _get(a.api, "/llm_usage").get("provedor") != "groq":
        raise SystemExit("backend não está com LLM_PROVIDER=groq")
    linhas = []
    for agente, q in amostra(a.n):
        u0 = _get(a.api, "/llm_usage")
        t0 = time.time()
        try:
            _post(a.api, "/chat", {"message": q, "include_history": False})
            ok = True
        except Exception as e:  # noqa: BLE001
            ok = str(e)[:120]
        u1 = _get(a.api, "/llm_usage")
        d = {"agente_log": agente, "pergunta": q, "ok": ok, "s": round(time.time() - t0, 1),
             "chamadas": u1["chamadas"] - u0["chamadas"],
             "tokens": (u1["prompt_tokens"] + u1["completion_tokens"])
                       - (u0["prompt_tokens"] + u0["completion_tokens"]),
             "rate_limited": u1["rate_limited"] - u0["rate_limited"],
             "por_papel": {p: v["chamadas"] - u0["por_papel"].get(p, {}).get("chamadas", 0)
                           for p, v in u1["por_papel"].items()}}
        linhas.append(d)
        print(json.dumps(d, ensure_ascii=False), flush=True)

    ch = [d["chamadas"] for d in linhas]
    tk = [d["tokens"] for d in linhas]
    print("\nperguntas:", len(linhas))
    print("chamadas/pergunta: média %.1f, mediana %s, máx %s" % (statistics.mean(ch), statistics.median(ch), max(ch)))
    print("tokens/pergunta:   média %.0f, mediana %s, máx %s" % (statistics.mean(tk), statistics.median(tk), max(tk)))
    out = ROOT / "eval/medir_chamadas_llm.json"
    out.write_text(json.dumps(linhas, ensure_ascii=False, indent=1), encoding="utf-8")
    print("salvo em", out)


if __name__ == "__main__":
    main()
