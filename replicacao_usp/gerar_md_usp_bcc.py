"""
Gera os markdowns de disciplina do currículo USP BCC (replicação p/ o paper CTIC)
a partir do JSON coletado do JupiterWeb (curso_usp_bcc.json).

Saída: markdown_usp_bcc/<codigo>.md no formato que src/knowledge_graph.py já parseia
(## Pré-requisitos → arestas PREREQUISITO_DE, confidence 1.0). Assim o MESMO
pipeline neurossimbólico (R1-R5, PyReason, validador) roda sobre outro currículo
sem tocar no motor — só dados novos.

Uso: python3 replicacao_usp/gerar_md_usp_bcc.py
"""

import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_JSON = os.path.join(ROOT, "replicacao_usp", "curso_usp_bcc.json")
EMENTAS_JSON = os.path.join(ROOT, "replicacao_usp", "ementas_usp_bcc.json")
OUT_DIR = os.path.join(ROOT, "markdown_usp_bcc")


def _md_disciplina(d, nome_por_codigo, curso):
    linhas = [f"# {d['nome']}", ""]
    linhas.append(f"**Código:** {d['codigo']}  ")
    linhas.append(f"**Curso(s):** {curso}  ")
    if d.get("semestre") is not None:
        linhas.append(f"**Termo:** {d['semestre']}  ")
    linhas.append("**Formato:** Disciplina  ")
    linhas.append("")
    prereqs = d.get("prereqs") or []
    if prereqs:
        linhas.append("## Pré-requisitos")
        linhas.append("")
        for cod in prereqs:
            nome = nome_por_codigo.get(cod, cod)
            linhas.append(f"- {nome} (Código: {cod})")
        linhas.append("")
    if d.get("ementa"):
        linhas.append("## Ementa")
        linhas.append("")
        linhas.append(d["ementa"])
        linhas.append("")
    return "\n".join(linhas)


def main():
    if not os.path.exists(SRC_JSON):
        print(f"Falta {SRC_JSON} (aguardando a coleta do JupiterWeb).")
        return
    data = json.load(open(SRC_JSON, encoding="utf-8"))
    discs = data["disciplinas"]
    curso = f"{data.get('curso','Bacharelado em Ciência da Computação')} ({data.get('instituicao','USP')})"
    nome_por_codigo = {d["codigo"]: d["nome"] for d in discs}

    # mescla ementas oficiais (JupiterWeb), se coletadas
    ementas = {}
    if os.path.exists(EMENTAS_JSON):
        ementas = json.load(open(EMENTAS_JSON, encoding="utf-8")).get("ementas", {})
    for d in discs:
        if not d.get("ementa") and ementas.get(d["codigo"]):
            d["ementa"] = ementas[d["codigo"]]

    os.makedirs(OUT_DIR, exist_ok=True)
    n = 0
    for d in discs:
        path = os.path.join(OUT_DIR, f"{d['codigo']}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_md_disciplina(d, nome_por_codigo, curso))
        n += 1

    # estatísticas rápidas do DAG (sanidade antes de rodar o pipeline)
    total_edges = sum(len(d.get("prereqs") or []) for d in discs)
    com_prereq = sum(1 for d in discs if d.get("prereqs"))
    print(f"{n} disciplinas → {OUT_DIR}")
    print(f"{total_edges} arestas de pré-requisito; {com_prereq} disciplinas com pré-requisito")
    # avisa se algum prereq aponta p/ código ausente (dado incompleto)
    faltando = sorted({c for d in discs for c in (d.get("prereqs") or [])
                       if c not in nome_por_codigo})
    if faltando:
        print(f"AVISO: pré-req para códigos fora da lista: {faltando}")


if __name__ == "__main__":
    main()
