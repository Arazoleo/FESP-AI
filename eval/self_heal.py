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
BOTTLENECKS = os.path.join(DATA, "conversation_bottlenecks.jsonl")
WORKORDERS = os.path.join(DATA, "self_heal_workorders.jsonl")
CURATION = os.path.join(DATA, "data_curation_queue.jsonl")

# gargalos de conversa com severidade >= isto viram work order. Tipo 'dado' vai
# p/ curadoria; tipo 'roteamento/qualidade/latencia/ux' é o valor NOVO que o
# oráculo de miss não enxerga (resposta confiante-errada, lentidão, abandono).
SEV_MIN = 4


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


def _branch_slug(rep):
    return "fix/" + "".join(
        c if c.isalnum() else "-" for c in (rep or "").lower())[:40].strip("-")


def _workorders_de_conversa():
    """Gargalos da análise de conversa (LLM) que o oráculo de miss NÃO vê:
    resposta confiante-errada, roteamento errado, latência, abandono. Agrega
    por (tipo, gargalo) e emite work order com a correção sugerida pelo LLM.
    Tipo 'dado' fica de fora (vira curadoria, não PR de código)."""
    bott = _load(BOTTLENECKS)
    agreg = {}
    for b in bott:
        d = b.get("diagnostico") or {}
        tipo = (d.get("tipo") or "").lower()
        sev = int(d.get("severidade", 0) or 0)
        if not d or tipo == "dado" or sev < SEV_MIN:
            continue
        garg = (d.get("gargalo") or "").strip()
        chave = (tipo, garg[:60])
        if chave not in agreg:
            agreg[chave] = {
                "representante": garg, "frequencia": 0, "exemplos": [],
                "tipo_hint": f"conversa:{tipo}", "origem": "conversa",
                "severidade": sev, "correcao_sugerida": d.get("correcao_sugerida", ""),
                "hint": _hint(garg),
                "branch_sugerida": _branch_slug(garg),
                "criado_em": datetime.now().isoformat(timespec="seconds"),
            }
        a = agreg[chave]
        a["frequencia"] += 1
        a["severidade"] = max(a["severidade"], sev)
        cid = b.get("cid", "")
        if cid and cid not in a["exemplos"]:
            a["exemplos"].append(cid)
    return list(agreg.values())


def main():
    tickets = _load(TICKETS)
    conversa = _workorders_de_conversa()
    if not tickets and not conversa:
        print("Sem tickets nem gargalos. Rode antes: python eval/triage_misses.py "
              "&& python eval/analisar_conversas.py")
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
            "origem": "miss",
            "hint": _hint(rep),
            "branch_sugerida": _branch_slug(rep),
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        })
    # + gargalos de conversa (qualidade/latência/ux/roteamento) — valor que o
    # oráculo de miss não captura. Ranqueia por impacto: miss por frequência,
    # conversa por severidade × ocorrências.
    workorders.extend(conversa)
    workorders.sort(key=lambda w: (w.get("frequencia", 0)
                    * (w.get("severidade", 1) if w.get("origem") == "conversa" else 1)),
                    reverse=True)

    with open(WORKORDERS, "w", encoding="utf-8") as f:
        for w in workorders:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")
    # a fila de curadoria começa vazia; o fixer a alimenta ao classificar como dado
    if not os.path.exists(CURATION):
        open(CURATION, "w").close()
    print(f"{len(workorders)} work orders ({len(tickets)} de miss + "
          f"{len(conversa)} de conversa) → {WORKORDERS}")
    print(f"fila de curadoria de dado (alimentada pelo fixer) → {CURATION}")

    print("\n== WORK ORDERS (ordem de impacto; tipo = palpite, fixer confirma) ==")
    for w in workorders[:12]:
        marca = "💬" if w.get("origem") == "conversa" else "  "
        extra = f"sev{w.get('severidade')}" if w.get("origem") == "conversa" \
            else f"hint={w['tipo_hint'][:18]}"
        print(f"  {marca}[{w['frequencia']}x] {w['representante'][:46]:46} {extra}")


if __name__ == "__main__":
    main()
