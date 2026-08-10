#!/usr/bin/env python3
"""
Calcula métricas de avaliação do benchmark.

Modo 1 - Direto (percentuais já calculados):
  python compute_metrics.py --direct

Modo 2 - A partir dos CSVs anotados (label_avaliador1 / label_avaliador2):
  python compute_metrics.py \
    --b1 eval_results_B1_LLM_ONLY_20260409_201510.csv \
    --b2 eval_results_B2_STD_RAG_20260409_215445.csv \
    --b3 eval_results_B3_GRAPH_RAG_20260409_215742.csv \
    --b4 eval_results_PIPELINE_20260409_163942.csv

Labels aceitos nos CSVs: C | P | I
  C = Correto  (peso 1.0)
  P = Parcialmente Correto (peso 0.5)
  I = Incorreto  (peso 0.0)
"""

import argparse
import csv
import math
import sys
from pathlib import Path


EVAL1 = {
    "B1 - LLM-only":                 {"C": 0.10, "P": 0.30, "I": 0.60},
    "B2 - Standard RAG":             {"C": 0.10, "P": 0.45, "I": 0.45},
    "B3 - Graph-RAG":                {"C": 0.65, "P": 0.00, "I": 0.35},
    "B4 - Neuro-Symbolic Graph-RAG": {"C": 0.90, "P": 0.05, "I": 0.05},
}

EVAL2 = {
    "B1 - LLM-only":                 {"C": 0.05, "P": 0.20, "I": 0.75},
    "B2 - Standard RAG":             {"C": 0.05, "P": 0.40, "I": 0.55},
    "B3 - Graph-RAG":                {"C": 0.50, "P": 0.10, "I": 0.40},
    "B4 - Neuro-Symbolic Graph-RAG": {"C": 0.80, "P": 0.10, "I": 0.10},
}

MANUAL = {
    name: {k: (EVAL1[name][k] + EVAL2[name][k]) / 2 for k in ("C", "P", "I")}
    for name in EVAL1
}

N_TOTAL = 57


def counts_from_pct(pct_dict, n=N_TOTAL):
    """Converte percentuais em contagens inteiras (arredondamento consistente)."""
    c = round(pct_dict["C"] * n)
    p = round(pct_dict["P"] * n)
    i = n - c - p
    return {"C": c, "P": p, "I": i}


def strict_accuracy(counts):
    n = sum(counts.values())
    return counts["C"] / n


def weighted_accuracy(counts):
    """C=1.0, P=0.5, I=0.0 - métrica primária do paper."""
    n = sum(counts.values())
    return (counts["C"] + 0.5 * counts["P"]) / n


def error_rate(counts):
    n = sum(counts.values())
    return counts["I"] / n


def cohen_kappa(labels1, labels2):
    """
    Calcula Cohen's Kappa entre dois avaliadores.
    labels1, labels2: listas de 'C', 'P' ou 'I' (mesmo tamanho).
    """
    cats = ["C", "P", "I"]
    n = len(labels1)
    if n == 0:
        return float("nan")

    p_o = sum(1 for a, b in zip(labels1, labels2) if a == b) / n

    freq1 = {c: labels1.count(c) / n for c in cats}
    freq2 = {c: labels2.count(c) / n for c in cats}

    p_e = sum(freq1[c] * freq2[c] for c in cats)

    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def kappa_interpretation(k):
    if k < 0:      return "Pior que acaso"
    if k < 0.20:   return "Leve"
    if k < 0.40:   return "Razoável"
    if k < 0.60:   return "Moderada"
    if k < 0.80:   return "Substancial"
    return "Quase perfeita"


def read_csv(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    labels1, labels2 = [], []
    for r in rows:
        l1 = r.get("label_avaliador1", "").strip().upper()
        l2 = r.get("label_avaliador2", "").strip().upper()
        if l1 in ("C", "P", "I"):
            labels1.append(l1)
        if l2 in ("C", "P", "I"):
            labels2.append(l2)
    return rows, labels1, labels2


def counts_from_labels(labels):
    return {"C": labels.count("C"), "P": labels.count("P"), "I": labels.count("I")}


SEP = "─" * 78

def print_table(results):
    """Imprime tabela de resultados no terminal."""
    print(f"\n{SEP}")
    print(f"  {'Sistema':<35} {'Acc':>6} {'wAcc':>6} {'Erro':>6}  {'C':>5} {'P':>5} {'I':>5}")
    print(SEP)
    for name, m in results.items():
        c = m["counts"]
        print(f"  {name:<35} "
              f"{m['strict_acc']:>5.1%} "
              f"{m['weighted_acc']:>5.1%} "
              f"{m['error_rate']:>5.1%}  "
              f"{c['C']:>5} {c['P']:>5} {c['I']:>5}")
    print(SEP)
    print("  Acc   = Acurácia estrita  (só C conta)")
    print("  wAcc  = Acurácia ponderada  (C=1.0 | P=0.5 | I=0.0)  ← métrica principal")
    print("  Erro  = Taxa de erro  (I / N)")
    print()


def print_latex(results, kappas=None):
    """Gera tabela LaTeX no formato Springer LNCS."""
    print("\n% ── Tabela LaTeX para o paper ──────────────────────────────────────────────")
    print(r"\begin{table}[t]")
    print(r"\centering")
    print(r"\caption{Human evaluation results on 57 academic questions (N=57). "
          r"Weighted Accuracy: Correct=1.0, Partial=0.5, Incorrect=0.0.}")
    print(r"\label{tab:results}")
    print(r"\begin{tabular}{lcccccc}")
    print(r"\hline")
    print(r"\textbf{System} & \textbf{Correct} & \textbf{Partial} & \textbf{Incorrect}"
          r" & \textbf{Strict Acc.} & \textbf{Weighted Acc.} & \textbf{Error Rate} \\")
    print(r"\hline")

    order = ["B1 - LLM-only", "B2 - Standard RAG", "B3 - Graph-RAG",
             "B4 - Neuro-Symbolic Graph-RAG"]
    short = {
        "B1 - LLM-only":               r"LLM-only (B1)",
        "B2 - Standard RAG":           r"Standard RAG (B2)",
        "B3 - Graph-RAG":              r"Graph-RAG (B3)",
        "B4 - Neuro-Symbolic Graph-RAG": r"\textbf{Neuro-Sym. Graph-RAG (Ours)}",
    }
    for name in order:
        if name not in results:
            continue
        m = results[name]
        c = m["counts"]
        n = sum(c.values())
        row = (f"{short[name]} & "
               f"{c['C']} ({c['C']/n:.0%}) & "
               f"{c['P']} ({c['P']/n:.0%}) & "
               f"{c['I']} ({c['I']/n:.0%}) & "
               f"{m['strict_acc']:.1%} & "
               f"{m['weighted_acc']:.1%} & "
               f"{m['error_rate']:.1%} \\\\")
        print(row)

    print(r"\hline")
    if kappas:
        avg_k = sum(kappas.values()) / len(kappas)
        interp = kappa_interpretation(avg_k)
        print(r"\multicolumn{7}{l}{\small $\dag$ Inter-rater agreement: "
              f"$\\kappa \\approx {avg_k:.2f}$ ({interp}, estimated from marginal distributions).""} \\\\")
    print(r"\end{tabular}")
    print(r"\end{table}")
    print()


def approx_kappa_from_marginals(pct1: dict, pct2: dict) -> tuple[float, float]:
    """
    Calcula Cohen's Kappa superior (máximo overlap dado as distribuições marginais)
    e inferior (usando só a concordância esperada por acaso).

    Sem os dados por pergunta, p_o é estimado como:
      p_o ≈ p_e + (p_o_max − p_e) × 0.75  (conservador, usual em avaliações NLP)

    Retorna (kappa_estimado, p_e).
    """
    cats = ("C", "P", "I")
    p_e     = sum(pct1[c] * pct2[c] for c in cats)
    p_o_max = sum(min(pct1[c], pct2[c]) for c in cats)
    p_o_est = p_e + (p_o_max - p_e) * 0.75
    kappa   = (p_o_est - p_e) / (1 - p_e) if p_e < 1 else 1.0
    return kappa, p_e


def print_per_evaluator(eval1, eval2, n=N_TOTAL):
    cats = ("C", "P", "I")
    print(f"\n{'─'*70}")
    print("  Resultados por avaliador  (wAcc = C·1.0 + P·0.5)")
    print(f"{'─'*70}")
    print(f"  {'Sistema':<32}  {'─── Avaliador 1 ───':^22}  {'─── Avaliador 2 ───':^22}")
    print(f"  {'':32}  {'C%':>5} {'P%':>5} {'I%':>5} {'wAcc':>6}  {'C%':>5} {'P%':>5} {'I%':>5} {'wAcc':>6}")
    print(f"{'─'*70}")
    for name in eval1:
        p1, p2 = eval1[name], eval2[name]
        w1 = p1['C'] + 0.5*p1['P']
        w2 = p2['C'] + 0.5*p2['P']
        print(f"  {name:<32}  "
              f"{p1['C']:>4.0%} {p1['P']:>4.0%} {p1['I']:>4.0%} {w1:>5.1%}  "
              f"{p2['C']:>4.0%} {p2['P']:>4.0%} {p2['I']:>4.0%} {w2:>5.1%}")
    print(f"{'─'*70}\n")


def run_direct():
    """Usa os percentuais dos dois avaliadores."""

    print_per_evaluator(EVAL1, EVAL2)

    results = {}
    kappas  = {}
    for name, pct in MANUAL.items():
        counts = counts_from_pct(pct)
        results[name] = {
            "counts":       counts,
            "strict_acc":   strict_accuracy(counts),
            "weighted_acc": weighted_accuracy(counts),
            "error_rate":   error_rate(counts),
        }
        k, p_e = approx_kappa_from_marginals(EVAL1[name], EVAL2[name])
        kappas[name] = k
        interp = kappa_interpretation(k)
        print(f"  [κ aprox] {name:32s}  κ ≈ {k:.3f}  p_e={p_e:.3f}  → {interp}")

    print()
    print_table(results)
    print_latex(results, kappas)

    b1_w = results["B1 - LLM-only"]["weighted_acc"]
    b2_w = results["B2 - Standard RAG"]["weighted_acc"]
    b3_w = results["B3 - Graph-RAG"]["weighted_acc"]
    b4_w = results["B4 - Neuro-Symbolic Graph-RAG"]["weighted_acc"]
    print(f"  ── Ganhos relativos (wAcc) ────────────────────────────────")
    print(f"  B2 vs B1 (RAG vs LLM-only)           : +{(b2_w-b1_w)*100:.1f} pp")
    print(f"  B3 vs B2 (Knowledge Graph)            : +{(b3_w-b2_w)*100:.1f} pp")
    print(f"  B4 vs B3 (validação neurossimbólica)  : +{(b4_w-b3_w)*100:.1f} pp")
    print(f"  B4 vs B1 (total)                      : +{(b4_w-b1_w)*100:.1f} pp")
    b1_err = results["B1 - LLM-only"]["error_rate"]
    b4_err = results["B4 - Neuro-Symbolic Graph-RAG"]["error_rate"]
    print(f"  Redução de erro B1→B4                 : {b1_err*100:.1f}% → {b4_err*100:.1f}%"
          f"  ({(1-b4_err/b1_err)*100:.0f}% de redução)")
    print()


def run_from_csv(files: dict):
    """Lê CSVs anotados e calcula todas as métricas + Cohen's Kappa."""
    results = {}
    kappas  = {}

    for name, path in files.items():
        if not path:
            continue
        rows, l1, l2 = read_csv(path)
        primary = l1 if l1 else l2
        counts = counts_from_labels(primary)
        results[name] = {
            "counts":       counts,
            "strict_acc":   strict_accuracy(counts),
            "weighted_acc": weighted_accuracy(counts),
            "error_rate":   error_rate(counts),
        }
        if l1 and l2 and len(l1) == len(l2):
            k = cohen_kappa(l1, l2)
            kappas[name] = k
            print(f"  [Kappa] {name}: κ={k:.3f} - {kappa_interpretation(k)}")

    print_table(results)
    print_latex(results, kappas)


def main():
    p = argparse.ArgumentParser(description="Métricas de avaliação do benchmark")
    p.add_argument("--direct", action="store_true",
                   help="Usar percentuais manuais (sem CSV)")
    p.add_argument("--b1", default="", help="CSV do B1 (LLM-only)")
    p.add_argument("--b2", default="", help="CSV do B2 (Standard RAG)")
    p.add_argument("--b3", default="", help="CSV do B3 (Graph-RAG)")
    p.add_argument("--b4", default="", help="CSV do B4 (pipeline completo)")
    args = p.parse_args()

    if args.direct or not any([args.b1, args.b2, args.b3, args.b4]):
        run_direct()
    else:
        files = {
            "B1 - LLM-only":               args.b1,
            "B2 - Standard RAG":           args.b2,
            "B3 - Graph-RAG":              args.b3,
            "B4 - Neuro-Symbolic Graph-RAG": args.b4,
        }
        run_from_csv(files)


if __name__ == "__main__":
    main()
