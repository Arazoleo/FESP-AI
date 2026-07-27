#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avaliação neurossimbólica para o paper BRACIS — FESP-AI (UNIFESP ICT).

Estende o dataset de 57 perguntas com ~20 novas perguntas que testam
especificamente as capacidades neurossimbólicas do sistema:
  - trajectory_planning   (BFS no DAG de pré-requisitos)
  - critical_disciplines  (regra de inferência ∀x: |dependents(x)| >= theta)
  - co_prerequisite       (disciplinas com pré-requisitos em comum)
  - prerequisite_chain    (cadeia direta de dependências)
  - discipline_docentes   (quem leciona, via KG)

Uso:
  python eval_neurosymbolic.py                        # API localhost:8000
  python eval_neurosymbolic.py --url http://IP:8000
  python eval_neurosymbolic.py --quick                # primeiras 20 perguntas
  python eval_neurosymbolic.py --judge                # habilita LLM-as-a-Judge
  python eval_neurosymbolic.py --judge --quick

Comparação de motores de reasoning (paper):
  # Baseline (motor Python clássico)
  FESPAI_REASONER=python  docker-compose up -d backend
  python eval_neurosymbolic.py --judge > results_python.json
  # PyReason (Datalog anotado, Aditya et al., AAAI 2023)
  FESPAI_REASONER=pyreason docker-compose up -d backend
  python eval_neurosymbolic.py --judge > results_pyreason.json
  # Comparar — diferenças aparecem em prereq/trajectory/co_prereq
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from statistics import median, mean as stat_mean

try:
    import requests
except ImportError:
    print("Instale requests: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Dataset base (57 perguntas originais)
# id, pergunta, agente_esperado, categoria, tipo_query, ground_truth_type
# ground_truth_type: "symbolic_verifiable" | "semantic"
# ---------------------------------------------------------------------------

DATASET_BASE = [
    # ementa — semantic (LLM precisa interpretar)
    (1,  "O que é Teoria dos Grafos?",                                        "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (2,  "O que é Matemática Discreta?",                                      "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (3,  "Descreva a disciplina Banco de Dados.",                             "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (4,  "O que é Redes de Computadores?",                                    "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (5,  "O que é Inteligência Artificial?",                                  "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (6,  "O que se estuda em Compiladores?",                                  "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (7,  "Qual a ementa de Álgebra Linear?",                                  "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (8,  "Me fale sobre a disciplina de Programação Orientada a Objetos.",    "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (9,  "Do que trata Lógica de Programação?",                               "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    (10, "Me fale sobre Matemática Discreta.",                                "disciplinas",  "ementa",             "factual_simples",   "semantic"),
    # pré-requisitos / dependentes — symbolic_verifiable (KG dá resposta exata)
    (11, "Quais são os pré-requisitos de Inteligência Artificial?",           "symbolic_kg",  "prereq",             "composicional",     "symbolic_verifiable"),
    (12, "Pré-requisitos de Banco de Dados?",                                 "symbolic_kg",  "prereq",             "composicional",     "symbolic_verifiable"),
    (13, "O que preciso fazer antes de Compiladores?",                        "symbolic_kg",  "prereq",             "composicional",     "symbolic_verifiable"),
    (14, "Pré-requisitos para cursar Algoritmos 2?",                          "symbolic_kg",  "prereq",             "composicional",     "symbolic_verifiable"),
    (15, "Quais disciplinas dependem de Cálculo 1?",                         "symbolic_kg",  "dependentes",        "composicional",     "symbolic_verifiable"),
    (16, "O que posso cursar depois de Algoritmos?",                          "symbolic_kg",  "dependentes",        "composicional",     "symbolic_verifiable"),
    (17, "Cadeia de pré-requisitos de Estrutura de Dados?",                   "symbolic_kg",  "prereq",             "composicional",     "symbolic_verifiable"),
    (18, "Disciplinas necessárias para fazer Cálculo 2?",                     "symbolic_kg",  "prereq",             "composicional",     "symbolic_verifiable"),
    # docentes: quem leciona — depende do KG + agente
    (19, "Quem leciona Redes de Computadores?",                               "symbolic_kg|docentes",     "quem_leciona",       "relacional",        "symbolic_verifiable"),
    (20, "Quem leciona Cálculo Numérico?",                                    "symbolic_kg|docentes",     "quem_leciona",       "relacional",        "symbolic_verifiable"),
    (21, "Quem dá aula de Sistemas Operacionais?",                            "symbolic_kg|docentes",     "quem_leciona",       "relacional",        "symbolic_verifiable"),
    (22, "Quais professores lecionam Banco de Dados?",                        "symbolic_kg|docentes",     "quem_leciona",       "relacional",        "symbolic_verifiable"),
    (23, "Docentes de Teoria dos Grafos?",                                    "symbolic_kg|docentes",     "quem_leciona",       "relacional",        "symbolic_verifiable"),
    (24, "Quem ensina Projeto e Análise de Algoritmos?",                      "symbolic_kg|docentes",     "quem_leciona",       "relacional",        "symbolic_verifiable"),
    # docentes: info/contato/áreas — semantic
    (25, "Quem é o professor Sanderson?",                                     "docentes",     "info",               "factual_simples",   "semantic"),
    (26, "Qual o email do professor Álvaro?",                                 "docentes",     "email",              "factual_simples",   "semantic"),
    (27, "Sala do professor Didier Vega?",                                    "docentes",     "sala",               "factual_simples",   "semantic"),
    (28, "Áreas de pesquisa do professor Rodrigo Colnago?",                   "docentes",     "areas",              "factual_simples",   "semantic"),
    (29, "Me fale sobre a professora Lilian Berton.",                         "docentes",     "info",               "factual_simples",   "semantic"),
    (30, "Contato do professor Elbert Macau?",                                "docentes",     "email",              "factual_simples",   "semantic"),
    (31, "Em que o Álvaro é especialista?",                                   "docentes",     "areas",              "factual_simples",   "semantic"),
    (32, "Professores que trabalham com inteligência artificial?",            "symbolic_kg|docentes",     "por_area",           "relacional",        "semantic"),
    (33, "Quem pesquisa machine learning?",                                   "symbolic_kg|docentes",     "por_area",           "relacional",        "semantic"),
    (34, "Docentes especialistas em redes?",                                  "symbolic_kg|docentes",     "por_area",           "relacional",        "semantic"),
    # docentes: disciplinas que X leciona
    (35, "Quais disciplinas o professor Sanderson leciona?",                  "docentes",     "disciplinas_docente","relacional",        "semantic"),
    (36, "Quais matérias o Sanderson dá?",                                    "docentes",     "disciplinas_docente","relacional",        "semantic"),
    (37, "O Sanderson dá aula de quê?",                                       "docentes",     "disciplinas_docente","relacional",        "semantic"),
    (38, "Disciplinas que o Rodrigo Colnago leciona?",                        "docentes",     "disciplinas_docente","relacional",        "semantic"),
    (39, "O professor Fabrício Olivetti leciona Banco de Dados?",             "docentes",     "sim_nao",            "relacional",        "semantic"),
    # cursos — alguns symbolic_verifiable (estrutura curricular via KG)
    (40, "Quais disciplinas do termo 3 de BCC?",                              "symbolic_kg",  "termo",              "composicional",     "symbolic_verifiable"),
    (41, "Disciplinas do termo 5 de Ciência da Computação?",                  "symbolic_kg",  "termo",              "composicional",     "symbolic_verifiable"),
    (42, "Quais disciplinas tem no termo 1 de BCC?",                          "symbolic_kg",  "termo",              "composicional",     "symbolic_verifiable"),
    (43, "Grade curricular de BCC?",                                          "symbolic_kg|cursos",       "matriz",             "composicional",     "semantic"),
    (44, "Grade completa de Ciência da Computação?",                          "symbolic_kg|cursos",       "matriz",             "composicional",     "semantic"),
    (45, "Quais cursos a UNIFESP oferece?",                                   "symbolic_kg",  "listar",             "factual_simples",   "symbolic_verifiable"),
    (46, "Matérias do primeiro semestre de computação?",                      "symbolic_kg",  "termo",              "composicional",     "symbolic_verifiable"),
    (47, "Quantos termos tem o curso de BCC?",                                "symbolic_kg|cursos",       "matriz",             "factual_simples",   "semantic"),
    (48, "Estrutura do curso de Engenharia de Computação?",                   "symbolic_kg|cursos",       "matriz",             "composicional",     "semantic"),
    (49, "Quem é o coordenador de BCC?",                                      "symbolic_kg|cursos",       "coordenador",        "relacional",        "semantic"),
    (50, "Coordenador do curso de Ciência da Computação?",                    "symbolic_kg|cursos",       "coordenador",        "relacional",        "semantic"),
    (51, "Eletivas de Engenharia de Computação?",                             "symbolic_kg|cursos",       "eletivas",           "composicional",     "semantic"),
    (52, "Quais são as eletivas de BCC?",                                     "symbolic_kg|cursos",       "eletivas",           "composicional",     "semantic"),
    # regimentos — semantic
    (53, "Quais artigos falam sobre matrícula?",                              "regimentos",   "artigos",            "factual_simples",   "semantic"),
    (54, "O que diz o regimento sobre estágio?",                              "regimentos",   "artigos",            "factual_simples",   "semantic"),
    (55, "Perguntas frequentes sobre TCC?",                                   "regimentos",   "faq",                "factual_simples",   "semantic"),
    (56, "Artigos sobre trancamento?",                                        "regimentos",   "artigos",            "factual_simples",   "semantic"),
    (57, "O que o regimento fala sobre diploma?",                             "regimentos",   "artigos",            "factual_simples",   "semantic"),
]

# ---------------------------------------------------------------------------
# Dataset neurossimbólico extendido (~20 novas perguntas)
# Todas devem acionar symbolic_kg.
# id, pergunta, agente_esperado, categoria, tipo_query, ground_truth_type,
# neurosym_feature  (campo adicional para Table 3)
# ---------------------------------------------------------------------------

DATASET_NEUROSYM = [
    # --- trajectory_planning (BFS no DAG de pré-requisitos) ---
    (58, "Como chego em Compiladores?",
         "symbolic_kg", "planejamento", "trajectory_planning", "symbolic_verifiable",
         "trajectory_planning"),
    (59, "Quero chegar em Banco de Dados, por onde começo?",
         "symbolic_kg", "planejamento", "trajectory_planning", "symbolic_verifiable",
         "trajectory_planning"),
    (60, "Caminho mínimo para Inteligência Artificial",
         "symbolic_kg", "planejamento", "trajectory_planning", "symbolic_verifiable",
         "trajectory_planning"),
    (61, "Já fiz Cálculo 1, como chego em Cálculo Numérico?",
         "symbolic_kg", "planejamento", "trajectory_planning", "symbolic_verifiable",
         "trajectory_planning"),
    (62, "Sequência de disciplinas para Projeto e Análise de Algoritmos",
         "symbolic_kg", "planejamento", "trajectory_planning", "symbolic_verifiable",
         "trajectory_planning"),
    # --- critical_disciplines (regra de inferência ∀x: |dependents(x)| ≥ θ) ---
    (63, "Quais disciplinas são críticas no currículo?",
         "symbolic_kg", "analise_curriculo", "critical_disciplines", "symbolic_verifiable",
         "critical_disciplines"),
    (64, "Quais as disciplinas mais importantes do curso?",
         "symbolic_kg", "analise_curriculo", "critical_disciplines", "symbolic_verifiable",
         "critical_disciplines"),
    (65, "Quais disciplinas desbloqueiam mais outras?",
         "symbolic_kg", "analise_curriculo", "critical_disciplines", "symbolic_verifiable",
         "critical_disciplines"),
    (66, "Quais matérias têm mais dependentes?",
         "symbolic_kg", "analise_curriculo", "critical_disciplines", "symbolic_verifiable",
         "critical_disciplines"),
    (67, "Disciplinas críticas do currículo de BCC",
         "symbolic_kg", "analise_curriculo", "critical_disciplines", "symbolic_verifiable",
         "critical_disciplines"),
    # --- co_prerequisite (disciplinas que compartilham pré-requisitos) ---
    (68, "Quais disciplinas têm os mesmos pré-requisitos de Cálculo 2?",
         "symbolic_kg", "co_prereq", "co_prerequisite", "symbolic_verifiable",
         "co_prerequisite"),
    (69, "Co-pré-requisitos de Algoritmos?",
         "symbolic_kg", "co_prereq", "co_prerequisite", "symbolic_verifiable",
         "co_prerequisite"),
    (70, "Quais disciplinas compartilham pré-requisitos com Álgebra Linear?",
         "symbolic_kg", "co_prereq", "co_prerequisite", "symbolic_verifiable",
         "co_prerequisite"),
    (71, "Co-requisitos de Estrutura de Dados?",
         "symbolic_kg", "co_prereq", "co_prerequisite", "symbolic_verifiable",
         "co_prerequisite"),
    (72, "Quais disciplinas têm pré-requisitos em comum com Lógica de Programação?",
         "symbolic_kg", "co_prereq", "co_prerequisite", "symbolic_verifiable",
         "co_prerequisite"),
    # --- prerequisite_chain (cadeia de dependência direta via KG) ---
    (73, "Quais disciplinas dependem de Cálculo 1?",
         "symbolic_kg", "prereq", "prerequisite_chain", "symbolic_verifiable",
         "prerequisite_chain"),
    (74, "O que desbloqueia Cálculo 2?",
         "symbolic_kg", "prereq", "prerequisite_chain", "symbolic_verifiable",
         "prerequisite_chain"),
    (75, "Quais cursos a UNIFESP ICT oferece?",
         "symbolic_kg", "listar", "prerequisite_chain", "symbolic_verifiable",
         "prerequisite_chain"),
    (76, "Disciplinas do 1o termo de BCC?",
         "symbolic_kg", "termo", "prerequisite_chain", "symbolic_verifiable",
         "prerequisite_chain"),
    # --- discipline_docentes (quem leciona via KG) ---
    (77, "Quais são os pré-requisitos diretos de Estrutura de Dados?",
         "symbolic_kg", "prereq", "prerequisite_chain", "symbolic_verifiable",
         "prerequisite_chain"),
    (78, "Quem leciona Compiladores?",
         "symbolic_kg", "quem_leciona", "discipline_docentes", "symbolic_verifiable",
         "discipline_docentes"),
    (79, "Quem dá aula de Inteligência Artificial?",
         "symbolic_kg", "quem_leciona", "discipline_docentes", "symbolic_verifiable",
         "discipline_docentes"),
    (80, "Docentes responsáveis por Lógica de Programação?",
         "symbolic_kg", "quem_leciona", "discipline_docentes", "symbolic_verifiable",
         "discipline_docentes"),
    (81, "Quais professores ensinam Banco de Dados?",
         "symbolic_kg", "quem_leciona", "discipline_docentes", "symbolic_verifiable",
         "discipline_docentes"),
    (82, "Quem leciona Algoritmos e Estruturas de Dados?",
         "symbolic_kg", "quem_leciona", "discipline_docentes", "symbolic_verifiable",
         "discipline_docentes"),
]

# ---------------------------------------------------------------------------
# Tuplas combinadas (base 57 + neurosym 20)
# Para iteração uniforme, o campo neurosym_feature é None para o dataset base
# e acrescido nas novas perguntas.
# ---------------------------------------------------------------------------

DATASET_FULL = [
    (*row, None) for row in DATASET_BASE
] + [
    row for row in DATASET_NEUROSYM
]


# ---------------------------------------------------------------------------
# Verificação simbólica (sem LLM judge)
# Retorna (verified: bool, reason: str)
# ---------------------------------------------------------------------------

def symbolic_verify(response, tipo_query, neurosym_feature):
    """
    Verifica heuristicamente se a resposta simbólica é válida.
    Lógica binária: VERIFIED (1) / NOT_VERIFIED (0).
    """
    if not response or len(response.strip()) < 10:
        return False, "empty_response"

    resp = response.strip()

    feature = neurosym_feature or tipo_query

    if feature == "trajectory_planning":
        # deve mencionar caminho, pré-requisito ou nomes de disciplinas
        keywords = ["caminho", "pré-requisito", "prerequisito", "sequência",
                    "sequencia", "→", "->", "antes", "ordem"]
        if any(k.lower() in resp.lower() for k in keywords):
            return True, "trajectory_keywords_found"
        # também válido se lista disciplinas em ordem
        if re.search(r"\d\.", resp) or "1." in resp:
            return True, "ordered_list_found"
        return False, "no_trajectory_indicators"

    if feature == "critical_disciplines":
        # deve conter tabela markdown ou lista de disciplinas com contagem
        if "|" in resp and "---" in resp:
            return True, "markdown_table_found"
        if re.search(r"(crítica|importante|dependente)", resp, re.I):
            if re.search(r"[-*•]\s+\w", resp):
                return True, "critical_list_found"
        return False, "no_critical_table_or_list"

    if feature == "co_prerequisite":
        # deve ser uma lista de disciplinas
        if re.search(r"[-*•]\s+\w", resp):
            return True, "list_found"
        if re.search(r"\d\.\s+\w", resp):
            return True, "numbered_list_found"
        if "nenhuma" in resp.lower() or "não há" in resp.lower():
            return True, "explicit_empty_result"
        return False, "no_list_found"

    if feature in ("prerequisite_chain", "prereq", "dependentes"):
        keywords = ["pré-requisito", "prerequisito", "dependente", "necessário",
                    "precisa", "antes", "desbloqueia", "disciplina"]
        if any(k.lower() in resp.lower() for k in keywords):
            return True, "prereq_keywords_found"
        if re.search(r"[-*•]\s+\w", resp) or re.search(r"\d\.\s+\w", resp):
            return True, "list_found"
        return False, "no_prereq_indicators"

    if feature == "discipline_docentes":
        keywords = ["docente", "professor", "leciona", "responsável", "ministra"]
        if any(k.lower() in resp.lower() for k in keywords):
            return True, "docente_keywords_found"
        return False, "no_docente_keywords"

    if feature in ("listar", "termo"):
        if re.search(r"[-*•]\s+\w", resp) or re.search(r"\d\.\s+\w", resp):
            return True, "list_found"
        if "|" in resp:
            return True, "table_found"
        return False, "no_list_or_table"

    # fallback: não vazia e não é mensagem de erro pura
    error_indicators = ["não encontr", "error", "falha", "timeout"]
    if any(e in resp.lower() for e in error_indicators):
        return False, "error_in_response"
    return True, "non_empty_response"


# ---------------------------------------------------------------------------
# Verificação de roteamento
# ---------------------------------------------------------------------------

def check_routing(agent_got: str, agent_expected: str) -> bool:
    """
    Retorna True se o agente obtido corresponde ao esperado.

    O esperado pode listar alternativas separadas por "|" (ex.: "symbolic_kg|docentes")
    para queries que o atalho neurossimbólico responde por design, mas cujo agente
    semântico também seria uma rota válida.
    """
    got = agent_got.strip().lower()
    return got in {a.strip().lower() for a in agent_expected.split("|")}


# ---------------------------------------------------------------------------
# Chamadas à API
# ---------------------------------------------------------------------------

def call_chat(base_url: str, question: str, timeout: int = 120) -> dict:
    try:
        r = requests.post(
            f"{base_url}/chat",
            json={"message": question, "include_history": False},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "TIMEOUT", "response": "", "active_agent": "ERROR"}
    except Exception as e:
        return {"error": str(e), "response": "", "active_agent": "ERROR"}


def call_chat_eval(base_url: str, question: str, timeout: int = 180) -> dict:
    try:
        r = requests.post(
            f"{base_url}/chat_eval",
            json={"message": question, "include_context": True, "include_sources": True},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "TIMEOUT", "response": "", "active_agent": "ERROR", "context": ""}
    except Exception as e:
        return {"error": str(e), "response": "", "active_agent": "ERROR", "context": ""}


def call_llm_judge(base_url: str, question: str, answer: str, evidence: str, timeout: int = 180) -> dict:
    try:
        r = requests.post(
            f"{base_url}/llm_judge",
            json={"question": question, "answer": answer, "evidence": evidence},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tabelas de resultados
# ---------------------------------------------------------------------------

def _safe_mean(values):
    vals = [v for v in values if v is not None]
    return stat_mean(vals) if vals else None


def _fmt(x, decimals: int = 2) -> str:
    if x is None:
        return "  N/A"
    return f"{x:.{decimals}f}"


def _pct(num: int, den: int) -> str:
    if den == 0:
        return " N/A%"
    return f"{num / den * 100:.1f}%"


def print_table1(rows: list[dict]) -> None:
    """TABLE 1: Query Distribution by Reasoning Path"""
    print("\n" + "=" * 70)
    print("  TABLE 1: Query Distribution by Reasoning Path")
    print("=" * 70)

    paths: dict[str, list[dict]] = {}
    for r in rows:
        p = r["agente_obtido"] if r["agente_obtido"] not in ("ERROR", "") else "ERROR"
        paths.setdefault(p, []).append(r)

    # expected vs obtained routing accuracy per path
    total = len(rows)
    header = f"{'Path':<22} | {'Queries':>7} | {'% Total':>8} | {'Avg Lat':>9} | {'Routing Acc':>12}"
    sep    = "-" * len(header)
    print(header)
    print(sep)

    for path in sorted(paths.keys()):
        items = paths[path]
        n = len(items)
        avg_lat = _safe_mean([r["latencia_s"] for r in items])
        routed_ok = sum(1 for r in items if r["routing_ok"])
        print(
            f"{path:<22} | {n:>7} | {_pct(n, total):>8} | {_fmt(avg_lat, 1) + 's':>9} | "
            f"{routed_ok}/{n} ({_pct(routed_ok, n):>6})"
        )
    print(sep)
    total_ok = sum(1 for r in rows if r["routing_ok"])
    print(f"{'TOTAL':<22} | {total:>7} | {'100.0%':>8} | "
          f"{_fmt(_safe_mean([r['latencia_s'] for r in rows]), 1) + 's':>9} | "
          f"{total_ok}/{total} ({_pct(total_ok, total):>6})")


def print_table2(rows: list[dict]) -> None:
    """TABLE 2: Quality Metrics by Path (LLM Judge, 1-5)"""
    judge_rows = [r for r in rows if r.get("judge_groundedness") not in (None, "", "")]
    if not judge_rows:
        print("\n[TABLE 2 skipped — no LLM judge scores. Re-run with --judge]")
        return

    print("\n" + "=" * 82)
    print("  TABLE 2: Quality Metrics by Reasoning Path (LLM Judge, scale 1-5)")
    print("=" * 82)

    buckets: dict[str, list[dict]] = {}
    for r in judge_rows:
        p = r["agente_obtido"] if r["agente_obtido"] not in ("ERROR", "") else "ERROR"
        buckets.setdefault(p, []).append(r)

    def _jmean(items, field):
        vals = []
        for it in items:
            v = it.get(field)
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
        return _safe_mean(vals)

    header = (
        f"{'Path':<22} | {'N':>4} | {'Groundedness':>13} | "
        f"{'Correctness':>12} | {'Completeness':>13} | {'Clarity':>8}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)
    for path in sorted(buckets.keys()):
        items = buckets[path]
        n = len(items)
        g  = _jmean(items, "judge_groundedness")
        c  = _jmean(items, "judge_correctness")
        cp = _jmean(items, "judge_completeness")
        cl = _jmean(items, "judge_clarity")
        print(
            f"{path:<22} | {n:>4} | {_fmt(g):>13} | {_fmt(c):>12} | "
            f"{_fmt(cp):>13} | {_fmt(cl):>8}"
        )
    print(sep)
    all_items = list(judge_rows)
    n = len(all_items)
    print(
        f"{'OVERALL':<22} | {n:>4} | {_fmt(_jmean(all_items, 'judge_groundedness')):>13} | "
        f"{_fmt(_jmean(all_items, 'judge_correctness')):>12} | "
        f"{_fmt(_jmean(all_items, 'judge_completeness')):>13} | "
        f"{_fmt(_jmean(all_items, 'judge_clarity')):>8}"
    )


def print_table3(rows: list[dict]) -> None:
    """TABLE 3: Neurosymbolic Features — Routing & Verification"""
    # Only neurosym questions (those with neurosym_feature set)
    ns_rows = [r for r in rows if r.get("neurosym_feature")]
    if not ns_rows:
        print("\n[TABLE 3 skipped — no neurosymbolic questions in run]")
        return

    print("\n" + "=" * 78)
    print("  TABLE 3: Neurosymbolic Features — Routing & Verification")
    print("=" * 78)

    features_order = [
        "trajectory_planning",
        "critical_disciplines",
        "co_prerequisite",
        "prerequisite_chain",
        "discipline_docentes",
    ]

    buckets: dict[str, list[dict]] = {}
    for r in ns_rows:
        f = r["neurosym_feature"]
        buckets.setdefault(f, []).append(r)

    header = (
        f"{'Feature':<25} | {'Exp. Agent':<12} | "
        f"{'Routed Correctly':>18} | {'Verified':>10}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    total_routed = 0
    total_verified = 0
    total_n = 0

    for feature in features_order:
        items = buckets.get(feature, [])
        if not items:
            continue
        n = len(items)
        exp_agent = items[0]["agente_esperado"]
        routed = sum(1 for r in items if r["routing_ok"])
        verified = sum(1 for r in items if r.get("symbolic_verified") == 1)
        total_routed += routed
        total_verified += verified
        total_n += n
        print(
            f"{feature:<25} | {exp_agent:<12} | "
            f"  {routed}/{n} ({_pct(routed, n):>6}){' ':>2} | "
            f"{verified}/{n} ({_pct(verified, n)})"
        )

    print(sep)
    print(
        f"{'TOTAL':<25} | {'symbolic_kg':<12} | "
        f"  {total_routed}/{total_n} ({_pct(total_routed, total_n):>6}){' ':>2} | "
        f"{total_verified}/{total_n} ({_pct(total_verified, total_n)})"
    )


def print_table4(rows: list[dict]) -> None:
    """TABLE 4: Latency by Reasoning Path (milliseconds)"""
    print("\n" + "=" * 72)
    print("  TABLE 4: Latency by Reasoning Path (milliseconds)")
    print("=" * 72)

    paths: dict[str, list[float]] = {}
    for r in rows:
        if r["agente_obtido"] in ("ERROR", ""):
            continue
        p = r["agente_obtido"]
        paths.setdefault(p, []).append(r["latencia_s"] * 1000)

    header = (
        f"{'Path':<22} | {'N':>4} | {'Min':>8} | {'Median':>8} | "
        f"{'Mean':>8} | {'P90':>8} | {'Max':>8}"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    for path in sorted(paths.keys()):
        lats = sorted(paths[path])
        n = len(lats)
        mn  = lats[0]
        mx  = lats[-1]
        med = median(lats)
        avg = stat_mean(lats)
        p90_idx = int(0.9 * n) - 1 if n > 1 else 0
        p90 = lats[max(0, p90_idx)]
        print(
            f"{path:<22} | {n:>4} | {mn:>6.0f}ms | {med:>6.0f}ms | "
            f"{avg:>6.0f}ms | {p90:>6.0f}ms | {mx:>6.0f}ms"
        )
    print(sep)


def print_overall_summary(rows: list[dict]) -> None:
    """OVERALL SUMMARY"""
    print("\n" + "=" * 60)
    print("  OVERALL SUMMARY")
    print("=" * 60)

    total = len(rows)
    routed_ok = sum(1 for r in rows if r["routing_ok"])
    sym_rows = [r for r in rows if r["agente_obtido"] == "symbolic_kg"]
    llm_rows = [r for r in rows if r["agente_obtido"] not in ("symbolic_kg", "ERROR", "")]

    sym_lats = [r["latencia_s"] for r in sym_rows] if sym_rows else [0]
    llm_lats = [r["latencia_s"] for r in llm_rows] if llm_rows else [0]
    sym_avg = stat_mean(sym_lats) if sym_lats else None
    llm_avg = stat_mean(llm_lats) if llm_lats else None

    speedup = (llm_avg / sym_avg) if (sym_avg and llm_avg and sym_avg > 0) else None

    print(f"  Total questions      : {total}")
    print(f"  Routing accuracy     : {routed_ok}/{total} ({_pct(routed_ok, total)})")
    print(f"  Symbolic path queries: {len(sym_rows)}/{total} ({_pct(len(sym_rows), total)} of total)")
    if sym_avg is not None:
        print(f"  Symbolic avg latency : {sym_avg:.2f}s ({sym_avg * 1000:.0f}ms)")
    if llm_avg is not None:
        print(f"  LLM agents avg lat   : {llm_avg:.2f}s ({llm_avg * 1000:.0f}ms)")
    if speedup is not None:
        print(f"  Symbolic speedup     : {speedup:.1f}x faster than LLM agents")

    ns_rows = [r for r in rows if r.get("neurosym_feature")]
    if ns_rows:
        ns_verified = sum(1 for r in ns_rows if r.get("symbolic_verified") == 1)
        print(f"  Neurosym questions   : {len(ns_rows)}")
        print(f"  Neurosym verified    : {ns_verified}/{len(ns_rows)} ({_pct(ns_verified, len(ns_rows))})")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(rows, prefix, base_url):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = f"{prefix}_{ts}.csv"
    json_path = f"{prefix}_{ts}.json"

    fieldnames = list(rows[0].keys()) if rows else []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "base_url": base_url,
                "total": len(rows),
                "results": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return csv_path, json_path


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(
    base_url: str,
    cases: list,
    use_judge: bool,
    verbose: bool = True,
) -> list[dict]:
    n = len(cases)
    rows = []

    for idx, entry in enumerate(cases, 1):
        # Unpack — base has 6 fields, neurosym has 7
        if len(entry) == 7:
            qid, question, agent_exp, categoria, tipo_query, ground_truth_type, neurosym_feature = entry
        else:
            qid, question, agent_exp, categoria, tipo_query, ground_truth_type, neurosym_feature = (*entry, None)

        if verbose:
            ns_tag = f" [{neurosym_feature}]" if neurosym_feature else ""
            print(f"  [{idx:3d}/{n}] {question[:55]:<55}{ns_tag}", end=" ", flush=True)

        t0 = time.time()

        if use_judge:
            data = call_chat_eval(base_url, question)
        else:
            data = call_chat(base_url, question)

        elapsed = round(time.time() - t0, 2)

        response     = (data.get("response") or "").strip()
        agent_got    = data.get("active_agent", "") or ""
        error        = data.get("error", "")
        context      = (data.get("context") or "").strip()
        sources      = "; ".join(data.get("sources") or [])

        routing_ok = check_routing(agent_got, agent_exp)

        # Symbolic verification for symbolic_kg responses
        sym_verified = None
        sym_reason   = ""
        if agent_got == "symbolic_kg" or ground_truth_type == "symbolic_verifiable":
            verified, reason = symbolic_verify(response, tipo_query, neurosym_feature)
            sym_verified = 1 if verified else 0
            sym_reason   = reason

        # LLM judge (optional, only if --judge and not symbolic)
        judge = {}
        if use_judge and not error and ground_truth_type == "semantic" and response:
            judge = call_llm_judge(base_url, question, response, context)

        if verbose:
            routing_sym = "✓" if routing_ok else "✗"
            sym_str = f" sym={sym_verified}" if sym_verified is not None else ""
            print(f"→ {agent_got:<15} {routing_sym}  ({elapsed}s){sym_str}")

        rows.append({
            "id":                  qid,
            "pergunta":            question,
            "agente_esperado":     agent_exp,
            "agente_obtido":       agent_got,
            "categoria":           categoria,
            "tipo_query":          tipo_query,
            "ground_truth_type":   ground_truth_type,
            "neurosym_feature":    neurosym_feature or "",
            "latencia_s":          elapsed,
            "routing_ok":          int(routing_ok),
            "symbolic_verified":   sym_verified if sym_verified is not None else "",
            "symbolic_reason":     sym_reason,
            "resposta":            response,
            "judge_groundedness":  judge.get("groundedness", ""),
            "judge_correctness":   judge.get("correctness", ""),
            "judge_completeness":  judge.get("completeness", ""),
            "judge_clarity":       judge.get("clarity", ""),
            "judge_rationale":     judge.get("rationale", ""),
            "sources":             sources,
            "erro":                error,
        })

    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Avaliação neurossimbólica BRACIS — FESP-AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--url",    default="http://localhost:8000", help="URL base da API")
    p.add_argument("--quick",  action="store_true", help="Só as primeiras 20 perguntas")
    p.add_argument("--judge",  action="store_true", help="Habilita LLM-as-a-Judge (mais lento)")
    p.add_argument("--output", default="eval_neurosymbolic", help="Prefixo do arquivo de saída")
    p.add_argument("--neurosym-only", action="store_true",
                   help="Roda apenas as 20 novas perguntas neurossimbólicas")
    args = p.parse_args()

    base_url = args.url.rstrip("/")

    if args.neurosym_only:
        cases = DATASET_NEUROSYM
        label = "neurossimbólico estendido"
    elif args.quick:
        cases = DATASET_FULL[:20]
        label = "quick (20 primeiras)"
    else:
        cases = DATASET_FULL
        label = "completo"

    n = len(cases)
    judge_str = " + LLM judge" if args.judge else ""
    print(f"\n{'='*65}")
    print(f"  Avaliação BRACIS Neurossimbólica — dataset {label}")
    print(f"  {n} perguntas via {base_url}{judge_str}")
    print(f"{'='*65}\n")

    rows = run_evaluation(base_url, cases, use_judge=args.judge)

    # Print all tables
    print_table1(rows)
    print_table2(rows)
    print_table3(rows)
    print_table4(rows)
    print_overall_summary(rows)

    # Save
    csv_path, json_path = save_results(rows, args.output, base_url)
    print(f"\n  CSV  salvo em : {csv_path}")
    print(f"  JSON salvo em : {json_path}\n")


if __name__ == "__main__":
    main()
