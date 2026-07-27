#!/usr/bin/env python3
"""
Avaliação dos 3 baselines para o paper BRACIS.

Sistemas avaliados:
  B1 — LLM-only     : Ollama direto, sem recuperação, sem KG
  B2 — Standard RAG : Hybrid Retriever (BM25+dense/RRF), sem KG, sem validação
  B3 — Graph-RAG    : KG + Hybrid Retriever, sem validação neurossimbólica

O dataset (57 perguntas) é o mesmo de eval_paper.py.

B1 chama o Ollama diretamente (localhost:11434).
B2 e B3 chamam o endpoint /chat_baseline da API (localhost:8000).

Uso:
  python eval_baselines.py                  # roda os 3 baselines
  python eval_baselines.py --system b1      # só LLM-only
  python eval_baselines.py --system b2      # só Standard RAG
  python eval_baselines.py --system b3      # só Graph-RAG
  python eval_baselines.py --quick          # primeiras 15 perguntas (teste)

Saída:
  eval_results_B1_<timestamp>.csv
  eval_results_B2_<timestamp>.csv
  eval_results_B3_<timestamp>.csv
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime

# ── Dataset (igual ao eval_paper.py) ─────────────────────────────────────────
DATASET = [
    (1,  "O que é Teoria dos Grafos?",                                        "disciplinas", "ementa",             "factual_simples"),
    (2,  "O que é Matemática Discreta?",                                      "disciplinas", "ementa",             "factual_simples"),
    (3,  "Descreva a disciplina Banco de Dados.",                             "disciplinas", "ementa",             "factual_simples"),
    (4,  "O que é Redes de Computadores?",                                    "disciplinas", "ementa",             "factual_simples"),
    (5,  "O que é Inteligência Artificial?",                                  "disciplinas", "ementa",             "factual_simples"),
    (6,  "O que se estuda em Compiladores?",                                  "disciplinas", "ementa",             "factual_simples"),
    (7,  "Qual a ementa de Álgebra Linear?",                                  "disciplinas", "ementa",             "factual_simples"),
    (8,  "Me fale sobre a disciplina de Programação Orientada a Objetos.",    "disciplinas", "ementa",             "factual_simples"),
    (9,  "Do que trata Lógica de Programação?",                               "disciplinas", "ementa",             "factual_simples"),
    (10, "Me fale sobre Matemática Discreta.",                                "disciplinas", "ementa",             "factual_simples"),
    (11, "Quais são os pré-requisitos de Inteligência Artificial?",           "disciplinas", "prereq",             "composicional"),
    (12, "Pré-requisitos de Banco de Dados?",                                 "disciplinas", "prereq",             "composicional"),
    (13, "O que preciso fazer antes de Compiladores?",                        "disciplinas", "prereq",             "composicional"),
    (14, "Pré-requisitos para cursar Algoritmos 2?",                          "disciplinas", "prereq",             "composicional"),
    (15, "Quais disciplinas dependem de Cálculo 1?",                         "disciplinas", "dependentes",        "composicional"),
    (16, "O que posso cursar depois de Algoritmos?",                          "disciplinas", "dependentes",        "composicional"),
    (17, "Cadeia de pré-requisitos de Estrutura de Dados?",                   "disciplinas", "prereq",             "composicional"),
    (18, "Disciplinas necessárias para fazer Cálculo 2?",                     "disciplinas", "prereq",             "composicional"),
    (19, "Quem leciona Redes de Computadores?",                               "docentes",    "quem_leciona",       "relacional"),
    (20, "Quem leciona Cálculo Numérico?",                                    "docentes",    "quem_leciona",       "relacional"),
    (21, "Quem dá aula de Sistemas Operacionais?",                            "docentes",    "quem_leciona",       "relacional"),
    (22, "Quais professores lecionam Banco de Dados?",                        "docentes",    "quem_leciona",       "relacional"),
    (23, "Docentes de Teoria dos Grafos?",                                    "docentes",    "quem_leciona",       "relacional"),
    (24, "Quem ensina Projeto e Análise de Algoritmos?",                      "docentes",    "quem_leciona",       "relacional"),
    (25, "Quem é o professor Sanderson?",                                     "docentes",    "info",               "factual_simples"),
    (26, "Qual o email do professor Álvaro?",                                 "docentes",    "email",              "factual_simples"),
    (27, "Sala do professor Didier Vega?",                                    "docentes",    "sala",               "factual_simples"),
    (28, "Áreas de pesquisa do professor Rodrigo Colnago?",                   "docentes",    "areas",              "factual_simples"),
    (29, "Me fale sobre a professora Lilian Berton.",                         "docentes",    "info",               "factual_simples"),
    (30, "Contato do professor Elbert Macau?",                                "docentes",    "email",              "factual_simples"),
    (31, "Em que o Álvaro é especialista?",                                   "docentes",    "areas",              "factual_simples"),
    (32, "Professores que trabalham com inteligência artificial?",            "docentes",    "por_area",           "relacional"),
    (33, "Quem pesquisa machine learning?",                                   "docentes",    "por_area",           "relacional"),
    (34, "Docentes especialistas em redes?",                                  "docentes",    "por_area",           "relacional"),
    (35, "Quais disciplinas o professor Sanderson leciona?",                  "docentes",    "disciplinas_docente","relacional"),
    (36, "Quais matérias o Sanderson dá?",                                    "docentes",    "disciplinas_docente","relacional"),
    (37, "O Sanderson dá aula de quê?",                                       "docentes",    "disciplinas_docente","relacional"),
    (38, "Disciplinas que o Rodrigo Colnago leciona?",                        "docentes",    "disciplinas_docente","relacional"),
    (39, "O professor Fabrício Olivetti leciona Banco de Dados?",             "docentes",    "sim_nao",            "relacional"),
    (40, "Quais disciplinas do termo 3 de BCC?",                              "cursos",      "termo",              "composicional"),
    (41, "Disciplinas do termo 5 de Ciência da Computação?",                  "cursos",      "termo",              "composicional"),
    (42, "Quais disciplinas tem no termo 1 de BCC?",                          "cursos",      "termo",              "composicional"),
    (43, "Grade curricular de BCC?",                                          "cursos",      "matriz",             "composicional"),
    (44, "Grade completa de Ciência da Computação?",                          "cursos",      "matriz",             "composicional"),
    (45, "Quais cursos a UNIFESP oferece?",                                   "cursos",      "listar",             "factual_simples"),
    (46, "Matérias do primeiro semestre de computação?",                      "cursos",      "termo",              "composicional"),
    (47, "Quantos termos tem o curso de BCC?",                                "cursos",      "matriz",             "factual_simples"),
    (48, "Estrutura do curso de Engenharia de Computação?",                   "cursos",      "matriz",             "composicional"),
    (49, "Quem é o coordenador de BCC?",                                      "cursos",      "coordenador",        "relacional"),
    (50, "Coordenador do curso de Ciência da Computação?",                    "cursos",      "coordenador",        "relacional"),
    (51, "Eletivas de Engenharia de Computação?",                             "cursos",      "eletivas",           "composicional"),
    (52, "Quais são as eletivas de BCC?",                                     "cursos",      "eletivas",           "composicional"),
    (53, "Quais artigos falam sobre matrícula?",                              "regimentos",  "artigos",            "factual_simples"),
    (54, "O que diz o regimento sobre estágio?",                              "regimentos",  "artigos",            "factual_simples"),
    (55, "Perguntas frequentes sobre TCC?",                                   "regimentos",  "faq",                "factual_simples"),
    (56, "Artigos sobre trancamento?",                                        "regimentos",  "artigos",            "factual_simples"),
    (57, "O que o regimento fala sobre diploma?",                             "regimentos",  "artigos",            "factual_simples"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save(rows, prefix, system_name):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = f"eval_results_{prefix}_{ts}.csv"
    json_path = f"eval_results_{prefix}_{ts}.json"
    fields = ["id","pergunta","categoria","tipo_query","latencia_s",
              "resposta","label_avaliador1","label_avaliador2","notas","erro"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"system": system_name, "timestamp": datetime.now().isoformat(),
                   "total": len(rows), "results": rows}, f, ensure_ascii=False, indent=2)
    total = len(rows)
    empty = sum(1 for r in rows if not r["resposta"] and not r["erro"])
    errors = sum(1 for r in rows if r["erro"])
    lat = round(sum(r["latencia_s"] for r in rows)/total, 2) if total else 0
    print(f"\n  ── {system_name} ──────────────────────────────────")
    print(f"  Total: {total} | Vazias: {empty} | Erros: {errors} | Latência média: {lat}s")
    print(f"  CSV  : {csv_path}")
    print(f"  JSON : {json_path}\n")
    return csv_path


# ── B1: LLM-only ──────────────────────────────────────────────────────────────

def run_b1(cases, model="gpt-oss:120b-cloud", ollama_url="http://localhost:11434"):
    """Chama Ollama diretamente, sem nenhum contexto recuperado."""
    import requests
    print(f"\n[B1 LLM-only] modelo={model}  perguntas={len(cases)}")

    PROMPT_TMPL = (
        "Você é um assistente acadêmico da UNIFESP ICT. "
        "Responda em português brasileiro de forma direta e objetiva.\n\n"
        "Pergunta: {question}\n\nResposta:"
    )

    rows = []
    for idx, (qid, question, _, categoria, tipo_query) in enumerate(cases, 1):
        print(f"  [{idx:2d}/{len(cases)}] {question[:55]}...", end=" ", flush=True)
        t0 = time.time()
        try:
            r = requests.post(
                f"{ollama_url}/api/generate",
                json={"model": model,
                      "prompt": PROMPT_TMPL.format(question=question),
                      "stream": False,
                      "options": {"temperature": 0.1, "num_predict": 1024}},
                timeout=120,
            )
            r.raise_for_status()
            response = r.json().get("response", "").strip()
            error = ""
        except Exception as e:
            response = ""
            error = str(e)
        elapsed = round(time.time() - t0, 2)
        print(f"({elapsed}s)")
        rows.append({"id": qid, "pergunta": question, "categoria": categoria,
                     "tipo_query": tipo_query, "latencia_s": elapsed,
                     "resposta": response, "label_avaliador1": "",
                     "label_avaliador2": "", "notas": "", "erro": error})

    return _save(rows, "B1_LLM_ONLY", "B1 — LLM-only")


# ── B2 e B3: via API /chat_baseline ──────────────────────────────────────────

def run_api_baseline(cases, system: str, base_url: str):
    """
    Chama o endpoint /chat_baseline da API em execução (Docker).
    system="b2" → Standard RAG (sem KG, sem validação)
    system="b3" → Graph-RAG (KG + RAG, sem validação neurossimbólica)
    """
    import requests

    labels = {
        "b2": ("B2_STD_RAG",   "B2 — Standard RAG"),
        "b3": ("B3_GRAPH_RAG", "B3 — Graph-RAG (sem validação neurossimbólica)"),
    }
    prefix, name = labels[system]
    print(f"\n[{name}]  perguntas={len(cases)}  endpoint={base_url}/chat_baseline")

    rows = []
    for idx, (qid, question, _, categoria, tipo_query) in enumerate(cases, 1):
        print(f"  [{idx:2d}/{len(cases)}] {question[:55]}...", end=" ", flush=True)
        t0 = time.time()
        try:
            r = requests.post(
                f"{base_url}/chat_baseline",
                json={"message": question, "system": system},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            response = data.get("response", "").strip()
            elapsed  = data.get("latency_s", round(time.time() - t0, 2))
            error    = ""
        except Exception as e:
            response = ""
            elapsed  = round(time.time() - t0, 2)
            error    = str(e)
        print(f"({elapsed}s)")
        rows.append({"id": qid, "pergunta": question, "categoria": categoria,
                     "tipo_query": tipo_query, "latencia_s": elapsed,
                     "resposta": response, "label_avaliador1": "",
                     "label_avaliador2": "", "notas": "", "erro": error})

    return _save(rows, prefix, name)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Baselines BRACIS — B1, B2, B3")
    p.add_argument("--system", choices=["b1","b2","b3","all"], default="all")
    p.add_argument("--quick",  action="store_true", help="Só os primeiros 15")
    p.add_argument("--model",  default="gpt-oss:120b-cloud",
                   help="Modelo Ollama para B1 (default: gpt-oss:120b-cloud)")
    p.add_argument("--ollama-url", default="http://localhost:11434",
                   help="URL do Ollama para B1")
    p.add_argument("--api-url",   default="http://localhost:8000",
                   help="URL da API FastAPI para B2/B3")
    args = p.parse_args()

    cases = DATASET[:15] if args.quick else DATASET

    run_b1_flag = args.system in ("b1", "all")
    run_b2_flag = args.system in ("b2", "all")
    run_b3_flag = args.system in ("b3", "all")

    if run_b1_flag:
        run_b1(cases, model=args.model, ollama_url=args.ollama_url)

    if run_b2_flag:
        run_api_baseline(cases, "b2", args.api_url.rstrip("/"))

    if run_b3_flag:
        run_api_baseline(cases, "b3", args.api_url.rstrip("/"))

    print("=" * 60)
    print("  Todos os baselines concluídos.")
    print("  Preencha label_avaliador1/2 com C / P / I em cada CSV.")
    print("=" * 60)


if __name__ == "__main__":
    main()
