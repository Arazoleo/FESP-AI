#!/usr/bin/env python3
"""
Roda LLM-as-a-Judge para o dataset do paper (57 perguntas).

Requer a API em execução, pois usa:
- /chat_eval para obter resposta + evidências (context)
- /llm_judge para pontuar groundedness/correctness/completeness/clarity

Uso:
  python eval_llm_judge.py                         # API localhost:8000
  python eval_llm_judge.py --url http://IP:8000
  python eval_llm_judge.py --quick                 # primeiras 15
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("Instale requests: pip install requests")
    sys.exit(1)


try:
    from eval_paper import DATASET
except Exception:
    DATASET = []

def split_validation_annotation(answer: str):
    """
    Se a resposta termina com um bloco de validação simbólica anexado pelo sistema,
    separa esse bloco para não penalizar o Judge por "não estar nas evidências".
    """
    if not answer:
        return "", ""
    s = answer.strip()
    marker = "\n\n---\n"
    idx = s.rfind(marker)
    if idx == -1:
        return s, ""
    tail = s[idx + len(marker) :].strip()
    if ("Verificado no Knowledge Graph" in tail) or ("⚠" in tail) or ("Atenção" in tail):
        head = s[:idx].strip()
        return head, tail
    return s, ""


def main():
    p = argparse.ArgumentParser(description="LLM-as-a-Judge - FESP-AI")
    p.add_argument("--url", default="http://localhost:8000", help="URL base da API")
    p.add_argument("--quick", action="store_true", help="Só os primeiros 15")
    p.add_argument("--output", default="eval_results_LLM_JUDGE", help="Prefixo do arquivo de saída")
    p.add_argument("--judge-model", default="", help="Modelo Ollama para o Judge (opcional)")
    args = p.parse_args()

    base_url = args.url.rstrip("/")
    cases = DATASET[:15] if args.quick else DATASET
    if not cases:
        raise SystemExit("Dataset não encontrado. Verifique eval_paper.py.")

    rows = []
    n = len(cases)
    print(f"\nLLM-as-a-Judge - {n} perguntas via {base_url}\n")

    for idx, (qid, question, agent_exp, categoria, tipo_query) in enumerate(cases, 1):
        print(f"  [{idx:2d}/{n}] {question[:60]}...", end=" ", flush=True)
        t0 = time.time()
        data = {}
        answer = ""
        answer_clean = ""
        evidence = ""
        try:
            r = requests.post(
                f"{base_url}/chat_eval",
                json={
                    "message": question,
                    "include_context": True,
                    "include_sources": True,
                },
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            answer = (data.get("response") or "").strip()
            evidence = (data.get("context") or "").strip()
            active_agent = data.get("active_agent", "")

            answer_clean, validation_note = split_validation_annotation(answer)
            evidence_for_judge = evidence
            if validation_note:
                evidence_for_judge = (
                    (evidence_for_judge + "\n\n" if evidence_for_judge else "")
                    + "[VALIDACAO SIMBOLICA]\n"
                    + validation_note
                )

            j = requests.post(
                f"{base_url}/llm_judge",
                json={
                    "question": question,
                    "answer": answer_clean,
                    "evidence": evidence_for_judge,
                    "judge_model": (args.judge_model or "").strip() or None,
                },
                timeout=180,
            )
            j.raise_for_status()
            judge = j.json()
            elapsed = round(time.time() - t0, 2)
            error = ""
        except Exception as e:
            answer = ""
            evidence = ""
            active_agent = "ERROR"
            judge = {}
            elapsed = round(time.time() - t0, 2)
            error = str(e)

        print(f"→ {active_agent} ({elapsed}s)")

        rows.append(
            {
                "id": qid,
                "pergunta": question,
                "agente_esperado": agent_exp,
                "agente_obtido": active_agent,
                "categoria": categoria,
                "tipo_query": tipo_query,
                "latencia_s": elapsed,
                "resposta": answer,
                "resposta_sem_validacao": answer_clean,
                "judge_groundedness": judge.get("groundedness", ""),
                "judge_correctness": judge.get("correctness", ""),
                "judge_completeness": judge.get("completeness", ""),
                "judge_clarity": judge.get("clarity", ""),
                "judge_unsupported_claims": judge.get("unsupported_claims", ""),
                "judge_rationale": judge.get("rationale", ""),
                "sources": "; ".join(data.get("sources") or []),
                "erro": error,
            }
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"{args.output}_{ts}.csv"
    json_path = f"{args.output}_{ts}.json"

    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "base_url": base_url,
                "total": n,
                "results": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nCSV salvo em : {csv_path}")
    print(f"JSON salvo em: {json_path}\n")


if __name__ == "__main__":
    main()
