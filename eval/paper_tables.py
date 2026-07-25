#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera tabelas prontas para publicação (BRACIS) a partir do JSON de avaliação
LLM-as-a-Judge existente.

Entrada padrão: eval_results_LLM_JUDGE_20260422_172052.json
(o arquivo com 57 perguntas e pontuações do Judge)

Uso:
  python paper_tables.py                                   # arquivo padrão
  python paper_tables.py eval_results_LLM_JUDGE_*.json   # outro arquivo
  python paper_tables.py --latex                          # saída também em LaTeX
  python paper_tables.py --all                            # todos os arquivos LLM_JUDGE*.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from statistics import mean as stat_mean, median, stdev

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _safe_mean(values):
    vals = [v for v in values if v is not None]
    return stat_mean(vals) if vals else None


def _safe_stdev(values):
    vals = [v for v in values if v is not None]
    return stdev(vals) if len(vals) >= 2 else None


def _safe_median(values):
    vals = [v for v in values if v is not None]
    return median(vals) if vals else None


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "  N/A%"
    return f"{num / den * 100:.1f}%"


def _fmt(x, decimals: int = 2) -> str:
    if x is None:
        return "  N/A"
    return f"{x:.{decimals}f}"


def _percentile(sorted_vals: list, p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = max(0, int(p * len(sorted_vals)) - 1)
    return sorted_vals[idx]


JUDGE_FIELDS = [
    "judge_groundedness",
    "judge_correctness",
    "judge_completeness",
    "judge_clarity",
    "judge_unsupported_claims",
]

# ---------------------------------------------------------------------------
# NOTE ON ROUTING ACCURACY
#
# The original eval_paper.py dataset (57 questions) was annotated before the
# neurosymbolic routing layer was introduced.  Many queries labeled
# "agente_esperado = disciplinas/docentes/cursos" are now correctly handled
# by symbolic_kg (faster, deterministic).  We therefore compute two views:
#
#   (A) "legacy routing accuracy" — agente_obtido == agente_esperado (as
#       recorded in the JSON).  This is intentionally low (≈33%) because
#       the KG now intercepts structural queries that the annotators expected
#       would go to LLM agents.
#
#   (B) "neurosymbolic routing accuracy" — symbolic_kg is treated as a
#       correct answer for any structural query (prereq / dependentes /
#       quem_leciona / termo / matriz / coordenador / eletivas / listar).
#       This reflects the system's actual intended behaviour.
# ---------------------------------------------------------------------------

STRUCTURAL_CATEGORIAS = {
    "prereq", "dependentes", "quem_leciona", "termo",
    "matriz", "coordenador", "eletivas", "listar", "sim_nao",
}


def neurosym_routing_ok(row: dict) -> bool:
    """
    Returns True if either:
    - agente_obtido == agente_esperado, OR
    - the query is structural and agente_obtido == 'symbolic_kg'
    """
    got = row.get("agente_obtido", "")
    exp = row.get("agente_esperado", "")
    if got == exp:
        return True
    cat = row.get("categoria", "")
    if got == "symbolic_kg" and cat in STRUCTURAL_CATEGORIAS:
        return True
    return False


# ---------------------------------------------------------------------------
# Table generators
# ---------------------------------------------------------------------------

def table1_query_distribution(rows: list[dict], title_suffix: str = "") -> str:
    """
    TABLE 1: Query distribution by reasoning path (agent obtained).
    Columns: Path | N | %Total | Avg Latency | Legacy Routing Acc | Neurosym Routing Acc
    """
    total = len(rows)
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        a = r.get("agente_obtido") or "UNKNOWN"
        buckets.setdefault(a, []).append(r)

    lines = []
    lines.append("")
    lines.append("=" * 85)
    lines.append(f"  TABLE 1: Query Distribution by Reasoning Path{title_suffix}")
    lines.append("=" * 85)

    header = (
        f"{'Path':<18} | {'N':>5} | {'%Total':>7} | "
        f"{'Avg Lat':>8} | {'Legacy Acc':>11} | {'NeurSym Acc':>12}"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    agent_order = ["symbolic_kg", "disciplinas", "docentes", "cursos", "regimentos", "UNKNOWN", "ERROR"]
    seen = set()
    ordered = [a for a in agent_order if a in buckets] + \
              [a for a in sorted(buckets) if a not in agent_order]

    total_legacy = 0
    total_neuro  = 0

    for agent in ordered:
        if agent not in buckets:
            continue
        seen.add(agent)
        items = buckets[agent]
        n = len(items)
        avg_lat = _safe_mean([r["latencia_s"] for r in items])
        legacy_ok = sum(1 for r in items if r.get("agente_obtido") == r.get("agente_esperado"))
        neuro_ok  = sum(1 for r in items if neurosym_routing_ok(r))
        total_legacy += legacy_ok
        total_neuro  += neuro_ok
        lines.append(
            f"{agent:<18} | {n:>5} | {_pct(n, total):>7} | "
            f"{_fmt(avg_lat, 2) + 's':>8} | "
            f"{legacy_ok}/{n} ({_pct(legacy_ok, n):>6}) | "
            f"{neuro_ok}/{n} ({_pct(neuro_ok, n):>6})"
        )

    lines.append(sep)
    lines.append(
        f"{'TOTAL':<18} | {total:>5} | {'100.0%':>7} | "
        f"{'':>8} | "
        f"{total_legacy}/{total} ({_pct(total_legacy, total):>6}) | "
        f"{total_neuro}/{total} ({_pct(total_neuro, total):>6})"
    )
    lines.append("")
    lines.append(
        "  NOTE: Legacy Acc = agente_obtido == agente_esperado (original annotation)."
    )
    lines.append(
        "        NeurSym Acc = symbolic_kg counts as correct for structural queries"
    )
    lines.append(
        "        (prereq / dependentes / quem_leciona / termo / matriz / etc.)."
    )
    return "\n".join(lines)


def table2_quality_metrics(rows: list[dict], title_suffix: str = "") -> str:
    """
    TABLE 2: Quality Metrics by Reasoning Path (LLM Judge, scale 1-5).
    """
    judge_rows = [
        r for r in rows
        if any(_as_float(r.get(f)) is not None for f in JUDGE_FIELDS)
    ]
    if not judge_rows:
        return "\n[TABLE 2 skipped — no LLM judge scores in this file]\n"

    buckets: dict[str, list[dict]] = {}
    for r in judge_rows:
        a = r.get("agente_obtido") or "UNKNOWN"
        buckets.setdefault(a, []).append(r)

    def _jmean(items, field):
        return _safe_mean([_as_float(it.get(field)) for it in items])

    lines = []
    lines.append("")
    lines.append("=" * 85)
    lines.append(f"  TABLE 2: Quality Metrics by Reasoning Path — LLM Judge (1–5){title_suffix}")
    lines.append("=" * 85)

    header = (
        f"{'Path':<18} | {'N':>4} | "
        f"{'Groundedness':>13} | {'Correctness':>12} | "
        f"{'Completeness':>13} | {'Clarity':>8} | {'Unsupported':>12}"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    agent_order = ["symbolic_kg", "disciplinas", "docentes", "cursos", "regimentos"]
    ordered = [a for a in agent_order if a in buckets] + \
              [a for a in sorted(buckets) if a not in agent_order]

    for agent in ordered:
        if agent not in buckets:
            continue
        items = buckets[agent]
        n = len(items)
        g  = _jmean(items, "judge_groundedness")
        c  = _jmean(items, "judge_correctness")
        cp = _jmean(items, "judge_completeness")
        cl = _jmean(items, "judge_clarity")
        u  = _jmean(items, "judge_unsupported_claims")
        lines.append(
            f"{agent:<18} | {n:>4} | {_fmt(g):>13} | {_fmt(c):>12} | "
            f"{_fmt(cp):>13} | {_fmt(cl):>8} | {_fmt(u):>12}"
        )

    lines.append(sep)
    n_all = len(judge_rows)
    lines.append(
        f"{'OVERALL':<18} | {n_all:>4} | "
        f"{_fmt(_jmean(judge_rows, 'judge_groundedness')):>13} | "
        f"{_fmt(_jmean(judge_rows, 'judge_correctness')):>12} | "
        f"{_fmt(_jmean(judge_rows, 'judge_completeness')):>13} | "
        f"{_fmt(_jmean(judge_rows, 'judge_clarity')):>8} | "
        f"{_fmt(_jmean(judge_rows, 'judge_unsupported_claims')):>12}"
    )
    return "\n".join(lines)


def table3_query_type_breakdown(rows: list[dict], title_suffix: str = "") -> str:
    """
    TABLE 3: Performance breakdown by query type (tipo_query).
    """
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        t = r.get("tipo_query") or "unknown"
        buckets.setdefault(t, []).append(r)

    def _jmean(items, field):
        return _safe_mean([_as_float(it.get(field)) for it in items])

    lines = []
    lines.append("")
    lines.append("=" * 85)
    lines.append(f"  TABLE 3: Performance by Query Type{title_suffix}")
    lines.append("=" * 85)

    header = (
        f"{'Query Type':<20} | {'N':>4} | "
        f"{'Avg Lat':>8} | {'% symKG':>8} | "
        f"{'Correctness':>12} | {'Completeness':>13} | {'Clarity':>8}"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    for tipo in sorted(buckets.keys()):
        items = buckets[tipo]
        n = len(items)
        avg_lat = _safe_mean([r["latencia_s"] for r in items])
        n_sym = sum(1 for r in items if r.get("agente_obtido") == "symbolic_kg")
        corr  = _jmean(items, "judge_correctness")
        compl = _jmean(items, "judge_completeness")
        clar  = _jmean(items, "judge_clarity")
        lines.append(
            f"{tipo:<20} | {n:>4} | "
            f"{_fmt(avg_lat, 2) + 's':>8} | "
            f"{_pct(n_sym, n):>8} | "
            f"{_fmt(corr):>12} | {_fmt(compl):>13} | {_fmt(clar):>8}"
        )

    lines.append(sep)
    return "\n".join(lines)


def table4_latency(rows: list[dict], title_suffix: str = "") -> str:
    """
    TABLE 4: Latency statistics by reasoning path (milliseconds).
    """
    buckets: dict[str, list[float]] = {}
    for r in rows:
        a = r.get("agente_obtido") or "UNKNOWN"
        buckets.setdefault(a, []).append(r["latencia_s"] * 1000)

    lines = []
    lines.append("")
    lines.append("=" * 78)
    lines.append(f"  TABLE 4: Latency by Reasoning Path (milliseconds){title_suffix}")
    lines.append("=" * 78)

    header = (
        f"{'Path':<18} | {'N':>4} | "
        f"{'Min':>7} | {'Median':>8} | {'Mean':>8} | "
        f"{'P90':>7} | {'Max':>7} | {'Std':>7}"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    agent_order = ["symbolic_kg", "disciplinas", "docentes", "cursos", "regimentos"]
    ordered = [a for a in agent_order if a in buckets] + \
              [a for a in sorted(buckets) if a not in agent_order]

    for agent in ordered:
        if agent not in buckets:
            continue
        lats = sorted(buckets[agent])
        n   = len(lats)
        mn  = lats[0]
        mx  = lats[-1]
        med = median(lats)
        avg = stat_mean(lats)
        p90 = _percentile(lats, 0.9)
        sd  = stdev(lats) if n >= 2 else 0.0
        lines.append(
            f"{agent:<18} | {n:>4} | "
            f"{mn:>5.0f}ms | {med:>6.0f}ms | {avg:>6.0f}ms | "
            f"{p90:>5.0f}ms | {mx:>5.0f}ms | {sd:>5.0f}ms"
        )

    lines.append(sep)

    # Symbolic speedup
    sym_lats = buckets.get("symbolic_kg", [])
    llm_lats = []
    for a, lats in buckets.items():
        if a not in ("symbolic_kg", "UNKNOWN", "ERROR"):
            llm_lats.extend(lats)
    if sym_lats and llm_lats:
        sym_avg = stat_mean(sym_lats)
        llm_avg = stat_mean(llm_lats)
        speedup = llm_avg / sym_avg if sym_avg > 0 else None
        if speedup:
            lines.append(
                f"\n  Symbolic path speedup vs LLM agents: {speedup:.1f}x "
                f"(symbolic mean={sym_avg:.0f}ms, LLM mean={llm_avg:.0f}ms)"
            )
    return "\n".join(lines)


def table5_error_analysis(rows: list[dict], title_suffix: str = "") -> str:
    """
    TABLE 5: Error analysis — empty/error responses by agent.
    """
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  TABLE 5: Error Analysis by Path{title_suffix}")
    lines.append("=" * 70)

    buckets: dict[str, list[dict]] = {}
    for r in rows:
        a = r.get("agente_obtido") or "UNKNOWN"
        buckets.setdefault(a, []).append(r)

    header = (
        f"{'Path':<18} | {'N':>4} | {'Errors':>7} | "
        f"{'Empty Resp':>11} | {'Avg Resp Len':>13}"
    )
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    agent_order = ["symbolic_kg", "disciplinas", "docentes", "cursos", "regimentos"]
    ordered = [a for a in agent_order if a in buckets] + \
              [a for a in sorted(buckets) if a not in agent_order]

    for agent in ordered:
        if agent not in buckets:
            continue
        items = buckets[agent]
        n = len(items)
        errors = sum(1 for r in items if r.get("erro", ""))
        empty  = sum(1 for r in items if not (r.get("resposta") or "").strip())
        lens   = [len((r.get("resposta") or "")) for r in items]
        avg_len = stat_mean(lens) if lens else 0
        lines.append(
            f"{agent:<18} | {n:>4} | {errors:>7} | "
            f"{empty:>11} | {avg_len:>11.0f}c"
        )

    lines.append(sep)
    return "\n".join(lines)


def overall_summary(rows: list[dict], json_path: str) -> str:
    total = len(rows)
    errors = sum(1 for r in rows if r.get("erro", ""))
    legacy_ok = sum(1 for r in rows if r.get("agente_obtido") == r.get("agente_esperado"))
    neuro_ok  = sum(1 for r in rows if neurosym_routing_ok(r))

    sym_rows = [r for r in rows if r.get("agente_obtido") == "symbolic_kg"]
    llm_rows = [r for r in rows if r.get("agente_obtido") not in ("symbolic_kg", "", None)]

    sym_lats = [r["latencia_s"] for r in sym_rows]
    llm_lats = [r["latencia_s"] for r in llm_rows]
    sym_avg  = stat_mean(sym_lats) if sym_lats else None
    llm_avg  = stat_mean(llm_lats) if llm_lats else None
    speedup  = (llm_avg / sym_avg) if (sym_avg and llm_avg and sym_avg > 0) else None

    def _jmean(items, field):
        return _safe_mean([_as_float(it.get(field)) for it in items])

    lines = []
    lines.append("")
    lines.append("=" * 65)
    lines.append("  OVERALL SUMMARY")
    lines.append("=" * 65)
    lines.append(f"  File                     : {os.path.basename(json_path)}")
    lines.append(f"  Total questions          : {total}")
    lines.append(f"  Errors / timeouts        : {errors}")
    lines.append(f"  Symbolic path queries    : {len(sym_rows)}/{total} ({_pct(len(sym_rows), total)})")
    lines.append(f"  LLM agent queries        : {len(llm_rows)}/{total} ({_pct(len(llm_rows), total)})")
    lines.append("")
    lines.append(f"  Routing accuracy (legacy): {legacy_ok}/{total} ({_pct(legacy_ok, total)})")
    lines.append(f"  Routing accuracy (neurosym): {neuro_ok}/{total} ({_pct(neuro_ok, total)})")
    lines.append("")
    if sym_avg is not None:
        lines.append(f"  Symbolic avg latency     : {sym_avg:.2f}s ({sym_avg*1000:.0f}ms)")
    if llm_avg is not None:
        lines.append(f"  LLM agents avg latency   : {llm_avg:.2f}s ({llm_avg*1000:.0f}ms)")
    if speedup is not None:
        lines.append(f"  Symbolic speedup         : {speedup:.1f}x faster than LLM agents")
    lines.append("")

    # Judge overall
    judge_rows = [r for r in rows if _as_float(r.get("judge_correctness")) is not None]
    if judge_rows:
        lines.append(f"  LLM judge coverage       : {len(judge_rows)}/{total} questions scored")
        for field, label in [
            ("judge_groundedness",   "  Avg groundedness        :"),
            ("judge_correctness",    "  Avg correctness         :"),
            ("judge_completeness",   "  Avg completeness        :"),
            ("judge_clarity",        "  Avg clarity             :"),
        ]:
            m = _jmean(judge_rows, field)
            lines.append(f"{label} {_fmt(m)}/5.00")

    lines.append("=" * 65)
    return "\n".join(lines)


def latex_table2(rows: list[dict]) -> str:
    """Generate LaTeX version of Table 2 (quality metrics)."""
    judge_rows = [r for r in rows if _as_float(r.get("judge_correctness")) is not None]
    if not judge_rows:
        return ""

    buckets: dict[str, list[dict]] = {}
    for r in judge_rows:
        a = r.get("agente_obtido") or "UNKNOWN"
        buckets.setdefault(a, []).append(r)

    def _jmean(items, field):
        return _safe_mean([_as_float(it.get(field)) for it in items])

    agent_order = ["symbolic_kg", "disciplinas", "docentes", "cursos", "regimentos"]
    ordered = [a for a in agent_order if a in buckets] + \
              [a for a in sorted(buckets) if a not in agent_order]

    lines = []
    lines.append(r"\begin{table}[h]")
    lines.append(r"\centering")
    lines.append(r"\caption{Quality Metrics by Reasoning Path (LLM-as-a-Judge, scale 1--5)}")
    lines.append(r"\label{tab:quality}")
    lines.append(r"\begin{tabular}{lrcccc}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Path} & \textbf{N} & \textbf{Groundedness} & \textbf{Correctness} & \textbf{Completeness} & \textbf{Clarity} \\")
    lines.append(r"\midrule")

    for agent in ordered:
        if agent not in buckets:
            continue
        items = buckets[agent]
        n  = len(items)
        g  = _jmean(items, "judge_groundedness")
        c  = _jmean(items, "judge_correctness")
        cp = _jmean(items, "judge_completeness")
        cl = _jmean(items, "judge_clarity")
        name = agent.replace("_", r"\_")
        lines.append(
            f"\\texttt{{{name}}} & {n} & {_fmt(g)} & {_fmt(c)} & {_fmt(cp)} & {_fmt(cl)} \\\\"
        )

    lines.append(r"\midrule")
    n_all = len(judge_rows)
    g  = _jmean(judge_rows, "judge_groundedness")
    c  = _jmean(judge_rows, "judge_correctness")
    cp = _jmean(judge_rows, "judge_completeness")
    cl = _jmean(judge_rows, "judge_clarity")
    lines.append(
        f"\\textbf{{Overall}} & {n_all} & {_fmt(g)} & {_fmt(c)} & {_fmt(cp)} & {_fmt(cl)} \\\\"
    )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def latex_table4(rows: list[dict]) -> str:
    """Generate LaTeX version of Table 4 (latency)."""
    buckets: dict[str, list[float]] = {}
    for r in rows:
        a = r.get("agente_obtido") or "UNKNOWN"
        buckets.setdefault(a, []).append(r["latencia_s"] * 1000)

    agent_order = ["symbolic_kg", "disciplinas", "docentes", "cursos", "regimentos"]
    ordered = [a for a in agent_order if a in buckets] + \
              [a for a in sorted(buckets) if a not in agent_order]

    lines = []
    lines.append(r"\begin{table}[h]")
    lines.append(r"\centering")
    lines.append(r"\caption{Latency by Reasoning Path (milliseconds)}")
    lines.append(r"\label{tab:latency}")
    lines.append(r"\begin{tabular}{lrrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Path} & \textbf{N} & \textbf{Min} & \textbf{Median} & \textbf{Mean} & \textbf{P90} & \textbf{Max} \\")
    lines.append(r"\midrule")

    for agent in ordered:
        if agent not in buckets:
            continue
        lats = sorted(buckets[agent])
        n   = len(lats)
        mn  = lats[0]
        mx  = lats[-1]
        med = median(lats)
        avg = stat_mean(lats)
        p90 = _percentile(lats, 0.9)
        name = agent.replace("_", r"\_")
        lines.append(
            f"\\texttt{{{name}}} & {n} & {mn:.0f} & {med:.0f} & {avg:.0f} & {p90:.0f} & {mx:.0f} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Process a single JSON file
# ---------------------------------------------------------------------------

def process_file(json_path: str, emit_latex: bool) -> None:
    try:
        data = json.load(open(json_path, encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] Cannot read {json_path}: {e}", file=sys.stderr)
        return

    rows = data.get("results", [])
    if not rows:
        print(f"[WARN] No results in {json_path}", file=sys.stderr)
        return

    ts = data.get("timestamp", "")
    suffix = f"  [{os.path.basename(json_path)}  ts={ts}]"

    print(f"\n{'#'*65}")
    print(f"#  File: {json_path}")
    print(f"#  Total records: {len(rows)}  |  Timestamp: {ts}")
    print(f"{'#'*65}")

    print(overall_summary(rows, json_path))
    print(table1_query_distribution(rows, suffix))
    print(table2_quality_metrics(rows, suffix))
    print(table3_query_type_breakdown(rows, suffix))
    print(table4_latency(rows, suffix))
    print(table5_error_analysis(rows, suffix))

    if emit_latex:
        print("\n" + "=" * 65)
        print("  LATEX OUTPUT")
        print("=" * 65)
        print("\n% TABLE 2 — Quality Metrics")
        print(latex_table2(rows))
        print("\n% TABLE 4 — Latency")
        print(latex_table4(rows))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEFAULT_JSON = "eval_results_LLM_JUDGE_20260422_172052.json"


def main():
    p = argparse.ArgumentParser(
        description="Gera tabelas de paper a partir do JSON de avaliação LLM-Judge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "files",
        nargs="*",
        help=f"Arquivo(s) JSON de avaliação. Padrão: {DEFAULT_JSON}",
    )
    p.add_argument(
        "--latex", action="store_true",
        help="Também imprime tabelas no formato LaTeX",
    )
    p.add_argument(
        "--all", action="store_true",
        help="Processa todos os arquivos eval_results_LLM_JUDGE*.json no diretório corrente",
    )
    args = p.parse_args()

    if args.all:
        files = sorted(glob.glob("eval_results_LLM_JUDGE*.json"))
        if not files:
            print("Nenhum arquivo eval_results_LLM_JUDGE*.json encontrado.", file=sys.stderr)
            sys.exit(1)
    elif args.files:
        files = args.files
    else:
        # default
        if not os.path.exists(DEFAULT_JSON):
            # try to find any LLM_JUDGE json
            candidates = sorted(glob.glob("eval_results_LLM_JUDGE*.json"))
            if candidates:
                files = [candidates[-1]]  # most recent
                print(f"[INFO] Default file not found. Using: {files[0]}", file=sys.stderr)
            else:
                print(
                    f"[ERROR] Default file '{DEFAULT_JSON}' not found and no "
                    "eval_results_LLM_JUDGE*.json files in current directory.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            files = [DEFAULT_JSON]

    for f in files:
        process_file(f, emit_latex=args.latex)


if __name__ == "__main__":
    main()
