"""
Orquestrador do loop de auto-correção (Fase 3, industrializada).

Lê os tickets da triagem (triage_tickets.jsonl) e SEPARA:
- CÓDIGO (roteamento/handler; a entidade existe na base) → work orders para o
  fixer, com dicas de diagnóstico;
- DADO (entidade/valor ausente) → fila de curadoria humana;
- INDEFINIDO → work order marcado para revisão humana.

NÃO altera código sozinho — prepara o trabalho. Cada work order é executada pelo
fixer (um agente, ou `claude -p` headless): diagnostica → corrige (grounding+
semântica, sem regex) → roda eval/fixer_pr.py (verifica + abre PR). Humano faz o
merge. É a fila de curadoria do SENSU aplicada ao código.

Uso:
    python eval/triage_misses.py     # (gera os tickets primeiro)
    python eval/self_heal.py         # separa e emite work orders + curadoria
"""

import os
import sys
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.getenv("FESPAI_DATA_DIR", os.path.join(ROOT, "chroma_db_unifesp"))
TICKETS = os.path.join(DATA, "triage_tickets.jsonl")
WORKORDERS = os.path.join(DATA, "self_heal_workorders.jsonl")
CURATION = os.path.join(DATA, "data_curation_queue.jsonl")


def _load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def _hint(rep):
    """Dica barata de onde olhar (o fixer aprofunda). Não é a correção."""
    return (
        "Diagnóstico sugerido: rode a pergunta contra o backend e veja o "
        "active_agent; cheque o roteamento (semantic_router.rotulo/"
        "rotulo_dominio, should_use_graph) e o handler do intent. Corrija por "
        "grounding no KG + exemplos semânticos (sem regex), cite a fonte. "
        "Depois: eval/gen_prod_tests.py + suíte + eval/fixer_pr.py (verifica+PR)."
    )


def main():
    tickets = _load(TICKETS)
    if not tickets:
        print("Sem tickets. Rode antes: python eval/triage_misses.py")
        return

    # Emite TODOS os tickets recorrentes como work orders ranqueadas. O `tipo`
    # da triagem é só um PALPITE (grounding de entidade é fraco: "congresso"
    # parecia dado mas era roteamento; "créditos álgebra linear 2" parecia
    # código mas é dado). Quem CONFIRMA código×dado é o fixer no diagnóstico;
    # se for dado, ele move o item pra fila de curadoria.
    workorders = []
    for t in tickets:
        rep = t.get("representante", "")
        workorders.append({
            "representante": rep, "frequencia": t.get("frequencia"),
            "exemplos": t.get("exemplos", []),
            "tipo_hint": t.get("tipo", "indefinido"),
            "hint": _hint(rep),
            "branch_sugerida": "fix/" + "".join(
                c if c.isalnum() else "-" for c in rep.lower())[:40].strip("-"),
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        })

    with open(WORKORDERS, "w", encoding="utf-8") as f:
        for w in workorders:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")
    # a fila de curadoria começa vazia; o fixer a alimenta ao classificar como dado
    if not os.path.exists(CURATION):
        open(CURATION, "w").close()
    print(f"{len(workorders)} work orders → {WORKORDERS}")
    print(f"fila de curadoria de dado (alimentada pelo fixer) → {CURATION}")

    print("\n== WORK ORDERS (ordem de impacto; tipo = palpite, fixer confirma) ==")
    for w in workorders[:10]:
        print(f"  [{w['frequencia']}x] {w['representante'][:50]:50} "
              f"hint={w['tipo_hint'][:22]}")


if __name__ == "__main__":
    main()
