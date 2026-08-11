"""
Trilhas por objetivo: dado um objetivo de carreira ou de estudo, monta uma
trilha de disciplinas usando a camada de conceitos do Knowledge Graph
(arestas ABORDA e REQUER_BASE) e sugere docentes pelas áreas de pesquisa.
"""

import re
import unicodedata
from typing import Dict, List, Optional


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    t = re.sub(r"[^\w\s-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _conceitos_no_texto(kg, texto: str, max_conceitos: int = 4) -> List[str]:
    q = f" {_norm(texto)} "
    achados = []
    for n, d in kg.graph.nodes(data=True):
        if d.get("tipo") != "conceito":
            continue
        nome = d.get("nome", "")
        if nome and f" {_norm(nome)} " in q:
            achados.append((len(nome), nome, n))
    achados.sort(reverse=True)
    filtrados = []
    for _, nome, n in achados:
        if any(nome in outro for outro in (f[0] for f in filtrados)):
            continue
        filtrados.append((nome, n))
    return filtrados[:max_conceitos]


def montar_trilha(kg, objetivo: str) -> Optional[Dict]:
    conceitos = _conceitos_no_texto(kg, objetivo)
    if not conceitos:
        return None
    g = kg.graph

    disciplinas: Dict[str, Dict] = {}
    for nome_c, cid in conceitos:
        for u, _, d in g.in_edges(cid, data=True):
            if d.get("relacao") != "ABORDA":
                continue
            nome_d = g.nodes[u].get("nome", u)
            eletiva = any(
                dd.get("relacao") == "ELETIVA_DE"
                for _, _, dd in g.in_edges(u, data=True)
            )
            termo = kg._termo_num(g.nodes[u])
            r = disciplinas.setdefault(nome_d, {
                "nome": nome_d,
                "termo": termo,
                "eletiva": eletiva,
                "conceitos": set(),
                "confidence": 0.0,
            })
            r["conceitos"].add(nome_c)
            r["confidence"] = max(r["confidence"], float(d.get("confidence", 1.0)))

    if not disciplinas:
        return None

    base = {}
    for info in list(disciplinas.values()):
        try:
            for b in kg.get_base_recomendada(info["nome"])[:2]:
                if b["nome"] not in disciplinas:
                    base[b["nome"]] = b
        except Exception:
            pass

    docentes = {}
    tokens_conceitos = {_norm(nc) for nc, _ in conceitos}
    for n, d in g.nodes(data=True):
        if d.get("tipo") != "area":
            continue
        area_norm = _norm(d.get("nome", ""))
        if not any(
            tc in area_norm or area_norm in tc for tc in tokens_conceitos if len(tc) > 3
        ):
            continue
        for u, _, dd in g.in_edges(n, data=True):
            if dd.get("relacao") == "ESPECIALISTA_EM":
                docentes.setdefault(
                    g.nodes[u].get("nome", u), set()
                ).add(d.get("nome", ""))

    ordenadas = sorted(
        (
            {**v, "conceitos": sorted(v["conceitos"])}
            for v in disciplinas.values()
        ),
        key=lambda x: (x["termo"] if x["termo"] is not None else 99, x["nome"]),
    )
    return {
        "objetivo": objetivo,
        "conceitos": [nc for nc, _ in conceitos],
        "disciplinas": ordenadas,
        "base": list(base.values()),
        "docentes": {k: sorted(v) for k, v in sorted(docentes.items())},
    }


def formatar_trilha(r: Dict) -> str:
    linhas = [
        f"**Trilha sugerida para: {', '.join(r['conceitos'])}**",
        "",
    ]
    if r["base"]:
        linhas.append("**Base recomendada primeiro:**")
        for b in r["base"]:
            linhas.append(
                f"- {b['nome']} ({', '.join(b['conceitos'])}; conf. {b['confidence']:.0%})"
            )
        linhas.append("")
    obrig = [d for d in r["disciplinas"] if not d["eletiva"]]
    elet = [d for d in r["disciplinas"] if d["eletiva"]]
    if obrig:
        linhas.append("**Na matriz (em ordem de termo):**")
        for d in obrig[:8]:
            termo = f"termo {d['termo']}" if d["termo"] is not None else "termo livre"
            linhas.append(f"- {d['nome']} ({termo}; {', '.join(d['conceitos'])})")
        linhas.append("")
    if elet:
        linhas.append("**Eletivas alinhadas ao objetivo:**")
        for d in elet[:8]:
            linhas.append(f"- {d['nome']} ({', '.join(d['conceitos'])})")
        linhas.append("")
    if r["docentes"]:
        linhas.append("**Docentes para IC/TCC nessas áreas:**")
        for nome, areas in list(r["docentes"].items())[:6]:
            linhas.append(f"- {nome} ({', '.join(areas)})")
        linhas.append("")
    linhas.append(
        "*Trilha inferida pelas arestas ABORDA/REQUER_BASE da camada de "
        "conceitos e pelas áreas de pesquisa dos docentes no Knowledge Graph. "
        "Clique nas disciplinas do chat para ver ementas e pré-requisitos.*"
    )
    return "\n".join(linhas)


_TRILHA_RES = [re.compile(p) for p in (
    r"\bquero\s+trabalhar\s+com\b",
    r"\bquero\s+seguir\s+(?:carreira|a\s+area)\b",
    r"\bme\s+especializar\s+em\b",
    r"\btrilha\s+(?:de|para|em)\b",
    r"\bquero\s+aprender\s+(?:mais\s+)?(?:sobre\s+)?\b",
    r"\bque\s+disciplinas\s+(?:cursar|fazer)\s+para\b",
)]


def is_trilha_request(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _TRILHA_RES)
