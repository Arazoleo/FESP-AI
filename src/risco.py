"""
Análise de risco de reprovação: o que uma reprovação em determinada disciplina
atrasa, calculado no DAG de pré-requisitos do Knowledge Graph.
"""

import re
import unicodedata
from typing import Dict, List, Optional


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


def analisar_reprovacao(kg, disciplina: str) -> Optional[Dict]:
    node = kg._find_node(disciplina, "disciplina")
    if not node:
        return None
    g = kg.graph
    nome = g.nodes[node].get("nome", disciplina)

    diretos = []
    for _, v, d in g.out_edges(node, data=True):
        if d.get("relacao") == "PREREQUISITO_DE":
            diretos.append(g.nodes[v].get("nome", v))
    diretos = sorted(set(diretos))

    transitivos = set()
    fila = [node]
    profundidade = {node: 0}
    while fila:
        atual = fila.pop()
        for _, v, d in g.out_edges(atual, data=True):
            if d.get("relacao") == "PREREQUISITO_DE" and v not in profundidade:
                profundidade[v] = profundidade[atual] + 1
                transitivos.add(g.nodes[v].get("nome", v))
                fila.append(v)

    cadeia_max = max(profundidade.values(), default=0)
    critica = len(diretos) >= 2

    try:
        paridade = kg.paridade_oferta(nome)
    except Exception:
        paridade = None

    return {
        "nome": nome,
        "diretos": diretos,
        "transitivos": sorted(transitivos),
        "cadeia_max": cadeia_max,
        "critica": critica,
        "paridade": paridade,
    }


def formatar_risco(r: Dict) -> str:
    linhas = [f"**Se você reprovar em {r['nome']}, o que trava:**", ""]
    if not r["diretos"]:
        linhas.append(
            f"Boa notícia: **nenhuma disciplina depende de {r['nome']}** no "
            "grafo. Uma reprovação não bloqueia outras UCs; o custo é refazer "
            "a própria disciplina (e o impacto no CR, que vale prioridade de "
            "vaga pelo art. 143 do Regulamento dos Cursos de Graduação)."
        )
        if r.get("paridade") in ("impar", "par"):
            nome_par = "ímpares" if r["paridade"] == "impar" else "pares"
            linhas.append(
                f"Atenção ao calendário: como é de termo "
                f"{'ímpar' if r['paridade'] == 'impar' else 'par'}, a oferta "
                f"esperada é só em semestres {nome_par} - refazer pode levar "
                "até 1 ano (vale confirmar com a coordenação)."
            )
    else:
        linhas.append(
            f"- **Bloqueio imediato**: {', '.join(r['diretos'])} "
            f"({len(r['diretos'])} disciplina(s) que exigem {r['nome']})"
        )
        extras = [t for t in r["transitivos"] if t not in r["diretos"]]
        if extras:
            linhas.append(
                f"- **Efeito em cascata**: {', '.join(extras[:8])}"
                + (f" e mais {len(extras) - 8}" if len(extras) > 8 else "")
            )
        if r.get("paridade") in ("impar", "par"):
            nome_par = "ímpares" if r["paridade"] == "impar" else "pares"
            linhas.append(
                f"- **Atraso potencial**: {r['nome']} é de termo "
                f"{'ímpar' if r['paridade'] == 'impar' else 'par'}, normalmente "
                f"ofertada só em semestres {nome_par} - reprovar tende a custar "
                f"**1 ano** até a próxima oferta, empurrando a cadeia à frente "
                f"(profundidade {r['cadeia_max']}) junto. Vale confirmar a "
                "oferta real com a coordenação."
            )
        else:
            linhas.append(
                f"- **Atraso potencial**: a cadeia à frente tem profundidade "
                f"{r['cadeia_max']}; reprovar tende a empurrar esse caminho em "
                "pelo menos 1 semestre (ou 1 ano, se a UC for anual na oferta)."
            )
        if r["critica"]:
            linhas.append(
                f"- ⚠ {r['nome']} é **disciplina crítica** pela regra R3 "
                f"(2 ou mais dependentes diretos): priorize-a."
            )
    linhas.append("")
    linhas.append(
        "*Regras aplicadas: `prereq_transitivity` (fecho no Knowledge Graph) e "
        "`critical_node` (θ = 2). A oferta real por semestre é definida pela "
        "coordenação.*"
    )
    return "\n".join(linhas)


_RISCO_RES = [
    re.compile(r"\bse\s+(?:eu\s+)?(?:reprovar|bombar|perder|nao\s+passar)\s+(?:em\s+|a\s+|o\s+)?(.+)"),
    re.compile(r"\b(?:reprovar|bombar|nao\s+passar)\s+em\s+(.+?)\s+(?:o\s+que|oq|atrasa|acontece)"),
    re.compile(r"\bo\s+que\s+acontece\s+se\s+(?:eu\s+)?(?:reprovar|bombar|nao\s+passar)\s+(?:em\s+)?(.+)"),
    re.compile(r"\bme\s+dar\s+mal\s+se\s+(?:eu\s+)?(?:reprovar|bombar|nao\s+passar)\s+(?:em\s+)?(.+)"),
]


def extrair_disciplina_risco(texto: str) -> Optional[str]:
    q = _norm(texto)
    for pat in _RISCO_RES:
        m = pat.search(q)
        if m:
            alvo = m.group(1)
            alvo = re.sub(
                r"\b(?:o\s+que|oq|que)\b.*$|\bacontece\b.*$|\batrasa\b.*$", "", alvo
            ).strip(" ?.!,")
            if alvo:
                return alvo
    return None


def is_risco_request(texto: str) -> bool:
    return extrair_disciplina_risco(texto) is not None
