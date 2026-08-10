#!/usr/bin/env python3
"""
Script de Avaliação do benchmark.

Roda as 57 perguntas do dataset contra o pipeline e gera:
  - eval_results_PIPELINE.csv   → respostas completas + colunas de label
  - eval_results_PIPELINE.json  → dump completo para uso posterior

Uso:
  python eval_paper.py                          # roda tudo via API localhost:8000
  python eval_paper.py --url http://IP:8000     # API remota
  python eval_paper.py --quick                  # só primeiros 15 (teste rápido)

Após rodar, abra o CSV e preencha as colunas:
  label_avaliador1  →  C = Correto / P = Parcialmente Correto / I = Incorreto
  label_avaliador2  →  igual (segundo avaliador)
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from typing import Optional

try:
    import requests
except ImportError:
    print("Instale requests: pip install requests")
    sys.exit(1)


DATASET = [
    (1,  "O que é Teoria dos Grafos?",                                        "disciplinas", "ementa",            "factual_simples"),
    (2,  "O que é Matemática Discreta?",                                      "disciplinas", "ementa",            "factual_simples"),
    (3,  "Descreva a disciplina Banco de Dados.",                             "disciplinas", "ementa",            "factual_simples"),
    (4,  "O que é Redes de Computadores?",                                    "disciplinas", "ementa",            "factual_simples"),
    (5,  "O que é Inteligência Artificial?",                                  "disciplinas", "ementa",            "factual_simples"),
    (6,  "O que se estuda em Compiladores?",                                  "disciplinas", "ementa",            "factual_simples"),
    (7,  "Qual a ementa de Álgebra Linear?",                                  "disciplinas", "ementa",            "factual_simples"),
    (8,  "Me fale sobre a disciplina de Programação Orientada a Objetos.",    "disciplinas", "ementa",            "factual_simples"),
    (9,  "Do que trata Lógica de Programação?",                               "disciplinas", "ementa",            "factual_simples"),
    (10, "Me fale sobre Matemática Discreta.",                                "disciplinas", "ementa",            "factual_simples"),
    (11, "Quais são os pré-requisitos de Inteligência Artificial?",           "disciplinas", "prereq",            "composicional"),
    (12, "Pré-requisitos de Banco de Dados?",                                 "disciplinas", "prereq",            "composicional"),
    (13, "O que preciso fazer antes de Compiladores?",                        "disciplinas", "prereq",            "composicional"),
    (14, "Pré-requisitos para cursar Algoritmos 2?",                          "disciplinas", "prereq",            "composicional"),
    (15, "Quais disciplinas dependem de Cálculo 1?",                         "disciplinas", "dependentes",       "composicional"),
    (16, "O que posso cursar depois de Algoritmos?",                          "disciplinas", "dependentes",       "composicional"),
    (17, "Cadeia de pré-requisitos de Estrutura de Dados?",                   "disciplinas", "prereq",            "composicional"),
    (18, "Disciplinas necessárias para fazer Cálculo 2?",                     "disciplinas", "prereq",            "composicional"),
    (19, "Quem leciona Redes de Computadores?",                               "docentes",    "quem_leciona",      "relacional"),
    (20, "Quem leciona Cálculo Numérico?",                                    "docentes",    "quem_leciona",      "relacional"),
    (21, "Quem dá aula de Sistemas Operacionais?",                            "docentes",    "quem_leciona",      "relacional"),
    (22, "Quais professores lecionam Banco de Dados?",                        "docentes",    "quem_leciona",      "relacional"),
    (23, "Docentes de Teoria dos Grafos?",                                    "docentes",    "quem_leciona",      "relacional"),
    (24, "Quem ensina Projeto e Análise de Algoritmos?",                      "docentes",    "quem_leciona",      "relacional"),
    (25, "Quem é o professor Sanderson?",                                     "docentes",    "info",              "factual_simples"),
    (26, "Qual o email do professor Álvaro?",                                 "docentes",    "email",             "factual_simples"),
    (27, "Sala do professor Didier Vega?",                                    "docentes",    "sala",              "factual_simples"),
    (28, "Áreas de pesquisa do professor Rodrigo Colnago?",                   "docentes",    "areas",             "factual_simples"),
    (29, "Me fale sobre a professora Lilian Berton.",                         "docentes",    "info",              "factual_simples"),
    (30, "Contato do professor Elbert Macau?",                                "docentes",    "email",             "factual_simples"),
    (31, "Em que o Álvaro é especialista?",                                   "docentes",    "areas",             "factual_simples"),
    (32, "Professores que trabalham com inteligência artificial?",            "docentes",    "por_area",          "relacional"),
    (33, "Quem pesquisa machine learning?",                                   "docentes",    "por_area",          "relacional"),
    (34, "Docentes especialistas em redes?",                                  "docentes",    "por_area",          "relacional"),
    (35, "Quais disciplinas o professor Sanderson leciona?",                  "docentes",    "disciplinas_docente","relacional"),
    (36, "Quais matérias o Sanderson dá?",                                    "docentes",    "disciplinas_docente","relacional"),
    (37, "O Sanderson dá aula de quê?",                                       "docentes",    "disciplinas_docente","relacional"),
    (38, "Disciplinas que o Rodrigo Colnago leciona?",                        "docentes",    "disciplinas_docente","relacional"),
    (39, "O professor Fabrício Olivetti leciona Banco de Dados?",             "docentes",    "sim_nao",           "relacional"),
    (40, "Quais disciplinas do termo 3 de BCC?",                              "cursos",      "termo",             "composicional"),
    (41, "Disciplinas do termo 5 de Ciência da Computação?",                  "cursos",      "termo",             "composicional"),
    (42, "Quais disciplinas tem no termo 1 de BCC?",                          "cursos",      "termo",             "composicional"),
    (43, "Grade curricular de BCC?",                                          "cursos",      "matriz",            "composicional"),
    (44, "Grade completa de Ciência da Computação?",                          "cursos",      "matriz",            "composicional"),
    (45, "Quais cursos a UNIFESP oferece?",                                   "cursos",      "listar",            "factual_simples"),
    (46, "Matérias do primeiro semestre de computação?",                      "cursos",      "termo",             "composicional"),
    (47, "Quantos termos tem o curso de BCC?",                                "cursos",      "matriz",            "factual_simples"),
    (48, "Estrutura do curso de Engenharia de Computação?",                   "cursos",      "matriz",            "composicional"),
    (49, "Quem é o coordenador de BCC?",                                      "cursos",      "coordenador",       "relacional"),
    (50, "Coordenador do curso de Ciência da Computação?",                    "cursos",      "coordenador",       "relacional"),
    (51, "Eletivas de Engenharia de Computação?",                             "cursos",      "eletivas",          "composicional"),
    (52, "Quais são as eletivas de BCC?",                                     "cursos",      "eletivas",          "composicional"),
    (53, "Quais artigos falam sobre matrícula?",                              "regimentos",  "artigos",           "factual_simples"),
    (54, "O que diz o regimento sobre estágio?",                              "regimentos",  "artigos",           "factual_simples"),
    (55, "Perguntas frequentes sobre TCC?",                                   "regimentos",  "faq",               "factual_simples"),
    (56, "Artigos sobre trancamento?",                                        "regimentos",  "artigos",           "factual_simples"),
    (57, "O que o regimento fala sobre diploma?",                             "regimentos",  "artigos",           "factual_simples"),
]


def run_pipeline(base_url: str, quick: bool, output_prefix: str):
    cases = DATASET[:15] if quick else DATASET
    n = len(cases)
    print(f"\n{'='*65}")
    print(f"  Avaliação - {n} perguntas via {base_url}")
    print(f"{'='*65}\n")

    rows = []
    for idx, (qid, question, agent_exp, categoria, tipo_query) in enumerate(cases, 1):
        print(f"  [{idx:2d}/{n}] {question[:60]}...", end=" ", flush=True)
        t0 = time.time()
        try:
            r = requests.post(
                f"{base_url}/chat",
                json={"message": question, "include_history": False},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            response  = (data.get("response") or "").strip()
            agent_got = data.get("active_agent", "")
            elapsed   = round(time.time() - t0, 2)
            error     = ""
        except Exception as e:
            response  = ""
            agent_got = "ERROR"
            elapsed   = round(time.time() - t0, 2)
            error     = str(e)

        agent_ok = "✓" if agent_got == agent_exp else "≠"
        print(f"→ {agent_got} {agent_ok}  ({elapsed}s)")

        rows.append({
            "id":               qid,
            "pergunta":         question,
            "agente_esperado":  agent_exp,
            "agente_obtido":    agent_got,
            "categoria":        categoria,
            "tipo_query":       tipo_query,
            "latencia_s":       elapsed,
            "resposta":         response,
            "label_avaliador1": "",
            "label_avaliador2": "",
            "notas":            "",
            "erro":             error,
        })

    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = f"{output_prefix}_{ts}.csv"
    json_path = f"{output_prefix}_{ts}.json"

    fieldnames = [
        "id", "pergunta", "agente_esperado", "agente_obtido",
        "categoria", "tipo_query", "latencia_s",
        "resposta",
        "label_avaliador1", "label_avaliador2", "notas", "erro",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "total": n,
            "results": rows,
        }, f, ensure_ascii=False, indent=2)

    total      = len(rows)
    agent_hits = sum(1 for r in rows if r["agente_obtido"] == r["agente_esperado"])
    errors     = sum(1 for r in rows if r["erro"])
    empty_     = sum(1 for r in rows if not r["resposta"] and not r["erro"])
    avg_lat    = round(sum(r["latencia_s"] for r in rows) / total, 2) if total else 0

    print(f"\n{'='*65}")
    print(f"  RESUMO")
    print(f"{'='*65}")
    print(f"  Total perguntas : {total}")
    print(f"  Agente correto  : {agent_hits}/{total}  ({agent_hits/total*100:.1f}%)")
    print(f"  Respostas vazias: {empty_}")
    print(f"  Erros           : {errors}")
    print(f"  Latência média  : {avg_lat}s")
    print(f"\n  CSV salvo em  : {csv_path}")
    print(f"  JSON salvo em : {json_path}")
    print(f"\n  ✎  Preencha as colunas  label_avaliador1  e  label_avaliador2")
    print(f"     com: C = Correto | P = Parcialmente Correto | I = Incorreto\n")


def main():
    p = argparse.ArgumentParser(description="Avaliação - FESP-AI")
    p.add_argument("--url",    default="http://localhost:8000", help="URL base da API")
    p.add_argument("--quick",  action="store_true",             help="Só os primeiros 15")
    p.add_argument("--output", default="eval_results_PIPELINE", help="Prefixo do arquivo de saída")
    args = p.parse_args()
    run_pipeline(args.url.rstrip("/"), args.quick, args.output)


if __name__ == "__main__":
    main()
