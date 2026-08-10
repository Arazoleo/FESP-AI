#!/usr/bin/env python3
"""
Resumo de métricas do LLM-as-a-Judge a partir do JSON gerado por eval_llm_judge.py.

Uso:
  python3 compute_judge_metrics.py eval_results_LLM_JUDGE_YYYYMMDD_HHMMSS.json
"""

import json
import sys
from collections import defaultdict


JUDGE_FIELDS = [
    "judge_groundedness",
    "judge_correctness",
    "judge_completeness",
    "judge_clarity",
    "judge_unsupported_claims",
]


def _as_float(x):
    try:
        return float(x)
    except Exception:
        return None


def mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def summarize(rows, key):
    buckets = defaultdict(list)
    for r in rows:
        buckets[r.get(key, "unknown")].append(r)

    out = {}
    for k, items in buckets.items():
        out[k] = {
            "n": len(items),
            **{
                f: mean([_as_float(it.get(f)) for it in items])
                for f in JUDGE_FIELDS
            },
        }
    return out


def print_summary(title, d):
    print(f"\n{title}")
    for k, m in sorted(d.items(), key=lambda kv: (-kv[1]["n"], str(kv[0]))):
        n = m["n"]
        g = m["judge_groundedness"]
        c = m["judge_correctness"]
        comp = m["judge_completeness"]
        cl = m["judge_clarity"]
        u = m["judge_unsupported_claims"]
        fmt = lambda x: "NA" if x is None else f"{x:.2f}"
        print(
            f"- {k} (n={n}): grounded={fmt(g)} corr={fmt(c)} compl={fmt(comp)} clarity={fmt(cl)} unsupported={fmt(u)}"
        )


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python3 compute_judge_metrics.py <eval_results_LLM_JUDGE_*.json>")

    path = sys.argv[1]
    data = json.load(open(path, encoding="utf-8"))
    rows = data.get("results", [])
    if not rows:
        raise SystemExit("JSON sem 'results'.")

    overall = {f: mean([_as_float(r.get(f)) for r in rows]) for f in JUDGE_FIELDS}
    print(f"Arquivo: {path}")
    print(f"Total: {len(rows)}")
    fmt = lambda x: "NA" if x is None else f"{x:.2f}"
    print(
        "Média geral: "
        f"grounded={fmt(overall['judge_groundedness'])} "
        f"corr={fmt(overall['judge_correctness'])} "
        f"compl={fmt(overall['judge_completeness'])} "
        f"clarity={fmt(overall['judge_clarity'])} "
        f"unsupported={fmt(overall['judge_unsupported_claims'])}"
    )

    by_type = summarize(rows, "tipo_query")
    by_agent = summarize(rows, "agente_obtido")

    print_summary("Por tipo_query", by_type)
    print_summary("Por agente_obtido", by_agent)


if __name__ == "__main__":
    main()
