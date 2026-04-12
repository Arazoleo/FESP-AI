#!/usr/bin/env python3
"""
Testes massivos do FESP-AI — exercita todos os tipos de documentos e agentes.

Executa dezenas de perguntas (disciplinas, docentes, cursos, regimentos) e
reporta erros, respostas vazias ou genéricas ("não tenho essa informação").

Uso:
  python run_mass_tests.py                    # todos os ~57 testes
  python run_mass_tests.py --quick           # só os primeiros 15
  python run_mass_tests.py -o resultado.json # salva relatório JSON
  python run_mass_tests.py --dry-run         # só valida lista (sem RAG/Ollama)

Requisitos para rodar os testes de verdade:
  - Dependências: pip install -r requirements.txt
  - Ollama rodando (ou OLLAMA_BASE_URL no .env) com o modelo configurado
  - Chroma/vector store e Knowledge Graph já sincronizados (rag.sync())
  Se usar Docker: subir o backend e chamar a API; ou rodar este script
  dentro do mesmo ambiente onde a API roda.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

# Garantir que o projeto está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Desabilitar warnings para saída limpa
os.environ.setdefault("PYTHONWARNINGS", "ignore")


def build_test_cases():
    """Monta lista de (pergunta, agente_esperado ou None, nota)."""
    return [
        # --- DISCIPLINAS: ementa ---
        ("O que é Teoria dos Grafos?", "disciplinas", "ementa"),
        ("O que é Matemática Discreta?", "disciplinas", "ementa"),
        ("Descreva a disciplina Banco de Dados.", "disciplinas", "ementa"),
        ("O que é Redes de Computadores?", "disciplinas", "ementa"),
        ("O que é Inteligência Artificial?", "disciplinas", "ementa"),
        ("O que se estuda em Compiladores?", "disciplinas", "ementa"),
        ("Qual a ementa de Álgebra Linear?", "disciplinas", "ementa"),
        ("Me fale sobre a disciplina de Programação Orientada a Objetos.", "disciplinas", "ementa"),
        ("Do que trata Lógica de Programação?", "disciplinas", "ementa"),
        ("Me fale sobre Matemática Discreta.", "disciplinas", "ementa"),
        # --- DISCIPLINAS: pré-requisitos e dependentes ---
        ("Quais são os pré-requisitos de Inteligência Artificial?", "disciplinas", "prereq"),
        ("Pré-requisitos de Banco de Dados?", "disciplinas", "prereq"),
        ("O que preciso fazer antes de Compiladores?", "disciplinas", "prereq"),
        ("Pré-requisitos para cursar Algoritmos 2?", "disciplinas", "prereq"),
        ("Quais disciplinas dependem de Cálculo 1?", "disciplinas", "dependentes"),
        ("O que posso cursar depois de Algoritmos?", "disciplinas", "dependentes"),
        ("Cadeia de pré-requisitos de Estrutura de Dados?", "disciplinas", "prereq"),
        ("Disciplinas necessárias para fazer Cálculo 2?", "disciplinas", "prereq"),
        # --- DOCENTES: quem leciona X ---
        ("Quem leciona Redes de Computadores?", "docentes", "quem_leciona"),
        ("Quem leciona Cálculo Numérico?", "docentes", "quem_leciona"),
        ("Quem dá aula de Sistemas Operacionais?", "docentes", "quem_leciona"),
        ("Quais professores lecionam Banco de Dados?", "docentes", "quem_leciona"),
        ("Docentes de Teoria dos Grafos?", "docentes", "quem_leciona"),
        ("Quem ensina Projeto e Análise de Algoritmos?", "docentes", "quem_leciona"),
        # --- DOCENTES: info, email, sala, áreas ---
        ("Quem é o professor Sanderson?", "docentes", "info"),
        ("Qual o email do professor Álvaro?", "docentes", "email"),
        ("Sala do professor Didier Vega?", "docentes", "sala"),
        ("Áreas de pesquisa do professor Rodrigo Colnago?", "docentes", "areas"),
        ("Me fale sobre a professora Lilian Berton.", "docentes", "info"),
        ("Contato do professor Elbert Macau?", "docentes", "email"),
        ("Em que o Álvaro é especialista?", "docentes", "areas"),
        ("Professores que trabalham com inteligência artificial?", "docentes", "por_area"),
        ("Quem pesquisa machine learning?", "docentes", "por_area"),
        ("Docentes especialistas em redes?", "docentes", "por_area"),
        # --- DOCENTES: disciplinas que X leciona ---
        ("Quais disciplinas o professor Sanderson leciona?", "docentes", "disciplinas_docente"),
        ("Quais matérias o Sanderson dá?", "docentes", "disciplinas_docente"),
        ("O Sanderson dá aula de quê?", "docentes", "disciplinas_docente"),
        ("Disciplinas que o Rodrigo Colnago leciona?", "docentes", "disciplinas_docente"),
        ("O professor Fabrício Olivetti leciona Banco de Dados?", "docentes", "sim_nao"),
        # --- CURSOS: termo, matriz, listar ---
        ("Quais disciplinas do termo 3 de BCC?", "cursos", "termo"),
        ("Disciplinas do termo 5 de Ciência da Computação?", "cursos", "termo"),
        ("Quais disciplinas tem no termo 1 de BCC?", "cursos", "termo"),
        ("Grade curricular de BCC?", "cursos", "matriz"),
        ("Grade completa de Ciência da Computação?", "cursos", "matriz"),
        ("Quais cursos a UNIFESP oferece?", "cursos", "listar"),
        ("Matérias do primeiro semestre de computação?", "cursos", "termo"),
        ("Quantos termos tem o curso de BCC?", "cursos", "matriz"),
        ("Estrutura do curso de Engenharia de Computação?", "cursos", "matriz"),
        # --- CURSOS: coordenador, eletivas ---
        ("Quem é o coordenador de BCC?", "cursos", "coordenador"),
        ("Coordenador do curso de Ciência da Computação?", "cursos", "coordenador"),
        ("Eletivas de Engenharia de Computação?", "cursos", "eletivas"),
        ("Quais são as eletivas de BCC?", "cursos", "eletivas"),
        # --- REGIMENTOS ---
        ("Quais artigos falam sobre matrícula?", "regimentos", "artigos"),
        ("O que diz o regimento sobre estágio?", "regimentos", "artigos"),
        ("Perguntas frequentes sobre TCC?", "regimentos", "faq"),
        ("Artigos sobre trancamento?", "regimentos", "artigos"),
        ("O que o regimento fala sobre diploma?", "regimentos", "artigos"),
    ]


def run_tests(quick: bool = False, output_path: Optional[str] = None):
    from src.multi_agent_rag import MultiAgentRAG
    from src.config import Config

    config = Config()
    print("Inicializando RAG (sync)...")
    rag = MultiAgentRAG(config=config)
    rag.sync()
    print("RAG pronto. Rodando testes...\n")

    cases = build_test_cases()
    if quick:
        cases = cases[:15]
        print("Modo rápido: apenas 15 primeiros testes.\n")

    results = []
    errors = []
    empty = []
    generic = []  # "não tenho essa informação"
    wrong_agent = []

    for i, (question, expected_agent, note) in enumerate(cases, 1):
        row = {
            "n": i,
            "question": question,
            "expected_agent": expected_agent,
            "note": note,
            "ok": False,
            "agent": None,
            "error": None,
            "response_preview": None,
        }
        try:
            out = rag.query_with_metadata(question)
            resp = (out.get("response") or "").strip()
            agent = out.get("active_agent", "")
            row["agent"] = agent
            row["response_preview"] = (resp[:200] + "…") if len(resp) > 200 else resp

            if not resp:
                empty.append(row)
                row["ok"] = False
            elif "não tenho essa informação" in resp.lower() or "nao tenho essa informacao" in resp.lower():
                generic.append(row)
                row["ok"] = False
            elif expected_agent and agent != expected_agent:
                wrong_agent.append(row)
                row["ok"] = False
            else:
                row["ok"] = True
        except Exception as e:
            row["error"] = str(e)
            errors.append(row)
            row["ok"] = False

        results.append(row)
        status = "✓" if row["ok"] else "✗"
        print(f"  [{status}] {i:3d} ({note}) {question[:55]}... → {row.get('agent') or 'ERR'}")

    # Relatório
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Total: {total} | OK: {passed} | Falhas: {total - passed}")
    if errors:
        print(f"\nErros (exceção): {len(errors)}")
        for r in errors:
            print(f"  - {r['question'][:50]}... → {r['error']}")
    if empty:
        print(f"\nRespostas vazias: {len(empty)}")
        for r in empty[:10]:
            print(f"  - {r['question'][:55]}...")
        if len(empty) > 10:
            print(f"  ... e mais {len(empty) - 10}")
    if generic:
        print(f"\nRespostas genéricas ('não tenho essa informação'): {len(generic)}")
        for r in generic[:10]:
            print(f"  - {r['question'][:55]}... (agente: {r.get('agent')})")
        if len(generic) > 10:
            print(f"  ... e mais {len(generic) - 10}")
    if wrong_agent:
        print(f"\nAgente diferente do esperado: {len(wrong_agent)}")
        for r in wrong_agent[:10]:
            print(f"  - Esperado: {r['expected_agent']} → obtido: {r.get('agent')} | {r['question'][:45]}...")
        if len(wrong_agent) > 10:
            print(f"  ... e mais {len(wrong_agent) - 10}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "errors": [{"n": r["n"], "question": r["question"], "error": r["error"]} for r in errors],
        "empty": [{"n": r["n"], "question": r["question"]} for r in empty],
        "generic": [{"n": r["n"], "question": r["question"], "agent": r.get("agent")} for r in generic],
        "wrong_agent": [
            {"n": r["n"], "question": r["question"], "expected": r["expected_agent"], "got": r.get("agent")}
            for r in wrong_agent
        ],
        "results": results,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nRelatório JSON salvo em: {output_path}")

    return report


def run_tests_via_api(
    quick: bool = False,
    output_path: Optional[str] = None,
    base_url: str = "http://localhost:8000",
):
    """Executa os mesmos testes via API (POST /chat). Requer backend rodando."""
    try:
        import requests
    except ImportError:
        print("Para --api instale: pip install requests")
        return

    cases = build_test_cases()
    if quick:
        cases = cases[:15]
        print("Modo rápido: 15 testes.\n")

    print(f"API: {base_url}/chat — rodando {len(cases)} testes...\n")
    results = []
    errors = []
    empty = []
    generic = []
    wrong_agent = []

    for i, (question, expected_agent, note) in enumerate(cases, 1):
        row = {
            "n": i,
            "question": question,
            "expected_agent": expected_agent,
            "note": note,
            "ok": False,
            "agent": None,
            "error": None,
            "response_preview": None,
        }
        try:
            r = requests.post(
                f"{base_url}/chat",
                json={"message": question, "include_history": False},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            resp = (data.get("response") or "").strip()
            agent = data.get("active_agent", "")
            row["agent"] = agent
            row["response_preview"] = (resp[:200] + "…") if len(resp) > 200 else resp

            if not resp:
                empty.append(row)
            elif "não tenho essa informação" in resp.lower() or "nao tenho essa informacao" in resp.lower():
                generic.append(row)
            elif expected_agent and agent != expected_agent:
                wrong_agent.append(row)
            else:
                row["ok"] = True
        except Exception as e:
            row["error"] = str(e)
            errors.append(row)

        results.append(row)
        status = "✓" if row["ok"] else "✗"
        print(f"  [{status}] {i:3d} ({note}) {question[:50]}... → {row.get('agent') or 'ERR'}")

    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    print("\n" + "=" * 70)
    print("RESUMO (via API)")
    print("=" * 70)
    print(f"Total: {total} | OK: {passed} | Falhas: {total - passed}")
    if errors:
        print(f"\nErros: {len(errors)}")
        for r in errors[:5]:
            print(f"  - {r['question'][:50]}... → {r['error']}")
    if empty:
        print(f"\nRespostas vazias: {len(empty)}")
    if generic:
        print(f"\nRespostas genéricas ('não tenho essa informação'): {len(generic)}")
    if wrong_agent:
        print(f"\nAgente diferente do esperado: {len(wrong_agent)}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "api",
        "base_url": base_url,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "errors": [{"n": r["n"], "question": r["question"], "error": r["error"]} for r in errors],
        "empty": [{"n": r["n"], "question": r["question"]} for r in empty],
        "generic": [{"n": r["n"], "question": r["question"], "agent": r.get("agent")} for r in generic],
        "wrong_agent": [
            {"n": r["n"], "question": r["question"], "expected": r["expected_agent"], "got": r.get("agent")}
            for r in wrong_agent
        ],
        "results": results,
    }
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nRelatório JSON: {output_path}")
    return report


def main():
    p = argparse.ArgumentParser(
        description="Testes massivos FESP-AI — disciplinas, docentes, cursos, regimentos."
    )
    p.add_argument("--quick", action="store_true", help="Só os primeiros 15 testes")
    p.add_argument("--output", "-o", default=None, help="Arquivo JSON de saída")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Só valida a lista de testes, sem carregar RAG (útil se o ambiente falhar)",
    )
    p.add_argument(
        "--api",
        action="store_true",
        help="Usar API em localhost:8000 em vez de carregar RAG neste processo",
    )
    p.add_argument("--api-url", default="http://localhost:8000", help="URL base da API (com --api)")
    args = p.parse_args()

    if args.dry_run:
        cases = build_test_cases()
        print(f"Dry-run: {len(cases)} casos de teste carregados.")
        for i, (q, ag, note) in enumerate(cases[:5], 1):
            print(f"  {i}. [{ag}] {note}: {q[:60]}...")
        print(f"  ... e mais {len(cases) - 5}.")
        return

    if args.api:
        run_tests_via_api(
            quick=args.quick,
            output_path=args.output,
            base_url=args.api_url.rstrip("/"),
        )
    else:
        run_tests(quick=args.quick, output_path=args.output)


if __name__ == "__main__":
    main()
