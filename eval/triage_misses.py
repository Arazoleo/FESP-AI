"""
Triagem post-hoc de uso (Fase 1 do loop de auto-correção).

Lê o misses_queue.jsonl (falhas) e o interactions.jsonl (todos os turnos), e
produz TICKETS DE PROBLEMA ranqueados:

- agrupa perguntas por SIMILARIDADE SEMÂNTICA (embeddings; não por regex), então
  paráfrases da mesma dor caem no mesmo cluster;
- ranqueia por frequência (impacto);
- separa GAP DE CÓDIGO vs GAP DE DADO por GROUNDING no KG: se a entidade da
  pergunta existe na base, o sistema tinha o dado e falhou em roteá-lo (código);
  se não existe, é curadoria de dado;
- resume métricas de uso (miss rate, latência, distribuição por agente).

Uso (no container, onde há embeddings/KG):
    python eval/triage_misses.py            # relatório + escreve tickets.jsonl
    python eval/triage_misses.py --no-embed # só frequência normalizada (sem KG)

Escreve {FESPAI_DATA_DIR}/triage_tickets.jsonl.
"""

import os
import sys
import json
import re
import collections
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DATA = os.getenv("FESPAI_DATA_DIR", os.path.join(ROOT, "chroma_db_unifesp"))
MISSES = os.path.join(DATA, "misses_queue.jsonl")
INTER = os.path.join(DATA, "interactions.jsonl")
TICKETS = os.path.join(DATA, "triage_tickets.jsonl")

USE_EMBED = "--no-embed" not in sys.argv


def _load(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower().strip(" ?.!,"))


def _cluster_semantic(perguntas, emb, limiar=0.82):
    """Agrupa perguntas por vizinho mais próximo (greedy) acima do limiar."""
    import numpy as np
    vecs = np.array(emb.embed_documents(perguntas), dtype="float32")
    vecs /= (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    clusters = []  # cada um: {"centroide_idx", "membros":[idx]}
    assigned = [-1] * len(perguntas)
    for i in range(len(perguntas)):
        if assigned[i] != -1:
            continue
        assigned[i] = len(clusters)
        membros = [i]
        for j in range(i + 1, len(perguntas)):
            if assigned[j] == -1 and float(vecs[i] @ vecs[j]) >= limiar:
                assigned[j] = len(clusters)
                membros.append(j)
        clusters.append(membros)
    return clusters


def _get_embeddings():
    try:
        from src.rag import RAGUnifesp
        r = RAGUnifesp()
        r.sync()
        return r.embeddings, r.knowledge_graph
    except Exception as e:
        print(f"[triage] sem embeddings/KG ({e}); usando frequência normalizada")
        return None, None


def _gap_tipo(pergunta, kg):
    """GAP DE DADO se a entidade não aterra no KG; senão GAP DE CÓDIGO (roteamento)
    ou INDEFINIDO. Grounding, não lexical."""
    if kg is None:
        return "indefinido"
    try:
        docs = kg.disciplinas_mencionadas(pergunta)
        prof = kg.docente_mencionado(pergunta)
        if docs or prof:
            return "codigo (entidade existe na base; roteamento/handler)"
    except Exception:
        pass
    return "dado? (nenhuma entidade da base aterrou)"


def main():
    misses = _load(MISSES)
    inter = _load(INTER)
    print(f"=== Triagem post-hoc ===")
    print(f"misses: {len(misses)} | interações: {len(inter)}")
    ts = [m.get("ts") for m in misses if m.get("ts")]
    if ts:
        print(f"período das falhas: {min(ts)[:10]} → {max(ts)[:10]}")

    # métricas de uso (do interactions.jsonl)
    if inter:
        n = len(inter)
        nmiss = sum(1 for r in inter if r.get("miss"))
        cids = len({r.get("cid") for r in inter})
        lat = sorted(r["latency_ms"] for r in inter if r.get("latency_ms"))
        p50 = lat[len(lat) // 2] if lat else 0
        p90 = lat[int(len(lat) * 0.9)] if lat else 0
        ag = collections.Counter(r.get("agent") for r in inter)
        print(f"\n-- uso -- turnos={n} conversas={cids} "
              f"miss_rate={nmiss/n:.0%} latência p50={p50}ms p90={p90}ms")
        print("   agentes:", dict(ag.most_common(6)))

    perguntas = [m.get("question", "") for m in misses if m.get("question")]
    if not perguntas:
        print("sem perguntas em miss."); return

    emb, kg = (_get_embeddings() if USE_EMBED else (None, None))

    if emb is not None:
        clusters = _cluster_semantic(perguntas, emb)
        grupos = []
        for membros in clusters:
            rep = perguntas[membros[0]]
            grupos.append((len(membros), rep, [perguntas[i] for i in membros]))
    else:
        c = collections.Counter(_norm(p) for p in perguntas)
        grupos = [(n, q, [q]) for q, n in c.most_common()]

    grupos.sort(key=lambda g: -g[0])
    print(f"\n-- tickets ranqueados (top 10 de {len(grupos)}) --")
    tickets = []
    for rank, (n, rep, membros) in enumerate(grupos[:10], 1):
        tipo = _gap_tipo(rep, kg)
        print(f"  #{rank} [{n}x] {rep[:58]}")
        print(f"       tipo: {tipo}")
        tickets.append({
            "rank": rank, "frequencia": n, "representante": rep,
            "tipo": tipo, "exemplos": membros[:5],
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
        })

    try:
        os.makedirs(os.path.dirname(TICKETS), exist_ok=True)
        with open(TICKETS, "w", encoding="utf-8") as f:
            for t in tickets:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        print(f"\ntickets escritos em {TICKETS}")
    except Exception as e:
        print(f"[triage] não escreveu tickets: {e}")


if __name__ == "__main__":
    main()
