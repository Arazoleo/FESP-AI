#!/usr/bin/env python3
"""
Gera comparativo de conversas para o paper BRACIS.
B2 = RAG padrão | B3 = Graph-RAG | FESP-AI = sistema neurossimbólico completo
"""
import requests, json, time, sys

BASE = "http://localhost:8000"

def ask(msg, conv_id=None):
    r = requests.post(f"{BASE}/chat", json={"message": msg, "conversation_id": conv_id}, timeout=120)
    d = r.json()
    return d.get("active_agent","?"), round(d.get("latency_s",0) or 0,2), d.get("response",""), d.get("conversation_id")

def ask_b(msg, system):
    r = requests.post(f"{BASE}/chat_baseline", json={"message": msg, "system": system}, timeout=120)
    d = r.json()
    return round(d.get("latency_s",0) or 0, 2), d.get("response","")

SEP  = "=" * 72
SEP2 = "-" * 72

SCENARIOS = [
    {
        "title": "Cenário 1 — Planejamento de Trajetória (BFS no DAG de pré-requisitos)",
        "question": "Como chego em Compiladores?",
        "why": "Requer busca BFS multi-hop no DAG de pré-requisitos. B2 não tem o grafo; B3 usa RAG + KG mas via LLM; FESP-AI executa BFS determinístico.",
    },
    {
        "title": "Cenário 2 — Trajetória com Contexto (disciplinas já cursadas)",
        "question": "Já fiz Cálculo 1, como chego em Cálculo Numérico?",
        "why": "Usa contexto do usuário para podar o BFS. B2 falha completamente; B3 ignora as disciplinas já cursadas; FESP-AI desconta Cálculo 1 do caminho.",
    },
    {
        "title": "Cenário 3 — Regra de Inferência: Disciplinas Críticas",
        "question": "Quais disciplinas são críticas no currículo de BCC?",
        "why": "Aplica regra ∀x: |dependentes(x)| ≥ θ sobre o KG. B2 sem informação; B3 correto mas 2-3× mais lento; FESP-AI executa diretamente no grafo.",
    },
    {
        "title": "Cenário 4 — Grafo de Dependências Diretas",
        "question": "Quais disciplinas dependem de Lógica de Programação?",
        "why": "Consulta aresta DEPENDE_DE no KG. Os três sistemas acertam, mas com latências muito diferentes.",
    },
]

MULTI_TURN = [
    "O que é Álgebra Linear?",
    "Quem leciona essa disciplina?",
    "E os pré-requisitos dela?",
    "Quais disciplinas dependem dela?",
]

rows_all = []

print(SEP)
print("  FESP-AI vs B2 (RAG Padrão) vs B3 (Graph-RAG) — Comparativo de Conversas")
print("  Para o paper BRACIS 2026")
print(SEP)

for sc in SCENARIOS:
    print(f"\n{'#'*72}")
    print(f"  {sc['title']}")
    print(f"  Pergunta: \"{sc['question']}\"")
    print(f"  Por quê: {sc['why']}")
    print(f"{'#'*72}\n")

    lat_b2, resp_b2 = ask_b(sc["question"], "b2")
    time.sleep(0.5)
    lat_b3, resp_b3 = ask_b(sc["question"], "b3")
    time.sleep(0.5)
    agent, lat_ns, resp_ns, _ = ask(sc["question"])

    rows_all.append({
        "scenario": sc["title"],
        "question": sc["question"],
        "b2_lat": lat_b2, "b2_resp": resp_b2[:400],
        "b3_lat": lat_b3, "b3_resp": resp_b3[:400],
        "ns_agent": agent, "ns_lat": lat_ns, "ns_resp": resp_ns[:400],
    })

    def show(label, lat, resp):
        lines = resp.strip().splitlines()
        preview = "\n    ".join(lines[:8])
        suffix = f"\n    ... [{len(lines)-8} linhas omitidas]" if len(lines)>8 else ""
        print(f"  [{label}] latência={lat}s")
        print(f"    {preview}{suffix}")
        print()

    show("B2  — RAG Padrão  ", lat_b2, resp_b2)
    show("B3  — Graph-RAG   ", lat_b3, resp_b3)
    show(f"FESP-AI/{agent:12}", lat_ns, resp_ns)

    speedup_b2 = round(lat_b2/lat_ns, 1) if lat_ns > 0 else "∞"
    speedup_b3 = round(lat_b3/lat_ns, 1) if lat_ns > 0 else "∞"
    print(f"  Speedup: FESP-AI {speedup_b2}× mais rápido que B2 | {speedup_b3}× mais rápido que B3")
    print(SEP2)
    time.sleep(1)

# ── Multi-turn ──────────────────────────────────────────────────────────
print(f"\n{'#'*72}")
print("  Cenário 5 — Conversa Multi-turno com Resolução de Contexto")
print("  (pronomes e referências a disciplinas mencionadas antes)")
print(f"{'#'*72}\n")

conv_id = None
turns = []
for msg in MULTI_TURN:
    agent, lat, resp, conv_id = ask(msg, conv_id)
    turns.append({"turn": msg, "agent": agent, "lat": lat, "resp": resp})
    print(f"  Usuário : {msg}")
    print(f"  [{agent}] ({lat}s)")
    preview = "\n           ".join(resp.strip().splitlines()[:5])
    print(f"           {preview}")
    print()
    time.sleep(0.5)

# ── Tabela resumo ────────────────────────────────────────────────────────
print(SEP)
print("  TABELA RESUMO — Comparativo de Sistemas")
print(SEP)
print(f"  {'Cenário':<38} | {'B2 lat':>7} | {'B3 lat':>7} | {'FESP lat':>8} | {'Agente':<14} | {'Speedup'}")
print(f"  {'-'*38}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}-+-{'-'*14}-+-{'-'*10}")
for r in rows_all:
    ns_lat = r["ns_lat"]
    b2_lat = r["b2_lat"]
    b3_lat = r["b3_lat"]
    sp_b2 = f"{b2_lat/ns_lat:.1f}×" if ns_lat > 0 else "∞"
    sp_b3 = f"{b3_lat/ns_lat:.1f}×" if ns_lat > 0 else "∞"
    title_short = r["scenario"].split("—")[1].strip()[:35]
    print(f"  {title_short:<38} | {b2_lat:>6}s | {b3_lat:>6}s | {ns_lat:>7}s | {r['ns_agent']:<14} | B2:{sp_b2} B3:{sp_b3}")

print(SEP)
print("  Multi-turn (5 turnos)")
for t in turns:
    print(f"    \"{t['turn'][:50]}\" → [{t['agent']}] {t['lat']}s")
print(SEP)

# salvar JSON
output = {
    "scenarios": rows_all,
    "multiturn": turns,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
with open("paper_conversations_output.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\n  Salvo em paper_conversations_output.json")
