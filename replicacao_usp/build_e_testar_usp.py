"""
Constrói o KG do currículo USP BCC (só markdown_usp_bcc/) e exercita as MESMAS
regras neurossimbólicas R1-R5 do pipeline da graduação, sem tocar no motor.
Prova de generalização p/ o paper CTIC (resposta à crítica de mono-domínio).

Roda no container (tem PyReason). Uso: python replicacao_usp/build_e_testar_usp.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_graph import KnowledgeGraph
from src.neurosymbolic_validator import _build_default_engine


def _linha(t):
    print("\n" + "=" * 66 + f"\n{t}\n" + "=" * 66)


def main():
    empty = os.path.join(ROOT, "replicacao_usp", "vazio")
    os.makedirs(empty, exist_ok=True)

    _linha("BUILD — KG do USP BCC (currículo 45052)")
    # Construção ISOLADA: só as disciplinas do USP. NÃO usamos
    # build_from_directories porque ele chama load_conceitos/
    # load_interdisciplinares, que leem seeds da UNIFESP e contaminariam o KG.
    from pathlib import Path
    kg = KnowledgeGraph()
    for md in sorted(Path(os.path.join(ROOT, "markdown_usp_bcc")).glob("*.md")):
        kg._process_discipline_file(md)
    stats = kg.get_stats()
    print(f"Grafo (isolado, só USP): {stats['disciplinas']} disciplinas, "
          f"{kg.graph.number_of_edges()} arestas")
    engine = _build_default_engine(kg)
    print(f"Motor de inferência: {type(engine).__name__} "
          f"(FESPAI_REASONER={os.environ.get('FESPAI_REASONER','pyreason')})")

    # ---- R1: fecho transitivo de pré-requisitos ----
    _linha("R1 — fecho transitivo (prereq_trans)")
    for alvo in ["Análise de Algoritmos", "Sistemas Operacionais",
                 "Conceitos Fundamentais de Linguagens de Programação"]:
        anc = kg.get_all_ancestors(alvo)
        print(f"  {alvo}: precisa de {sorted(anc)}")

    # ---- R3: nós críticos (>= 2 dependentes) ----
    _linha("R3 — disciplinas críticas (θ=2)")
    for nome, n in engine.critical_disciplines(min_dependents=2):
        print(f"  {nome}: {n} dependentes")

    # ---- R4: co-pré-requisitos ----
    _linha("R4 — co-pré-requisitos")
    for d in ["Introdução à Computação", "Álgebra Linear I",
              "Técnicas de Programação I"]:
        co = engine.find_co_prerequisites(d)
        print(f"  {d}: {co}")

    # ---- R5: plano mínimo (BFS topológico) + B2 confiança ----
    _linha("R5 — plano de estudos mínimo (do zero)")
    for alvo in ["Análise de Algoritmos", "Sistemas Operacionais"]:
        plano = engine.plan_minimal_path(alvo, [])
        print(f"  {alvo}:")
        if plano:
            for i, fase in enumerate(plano, 1):
                print(f"    fase {i}: {fase}")
            per, overall = engine.path_confidence(plano)
            print(f"    confiança do caminho: {overall:.2f} "
                  f"(curado=1.0){' · parciais='+str(per) if per else ''}")
        else:
            print("    (sem plano)")

    # ---- R2: desbloqueio dado um conjunto cursado ----
    _linha("R2 — desbloqueio (unlocked) após cursar o 1º semestre")
    cursado = ["Introdução à Computação", "Cálculo Diferencial e Integral I",
               "Vetores e Geometria"]
    unlocked = engine.derive_unlocked(cursado)
    print(f"  cursado {cursado}")
    print(f"  desbloqueadas: {sorted(unlocked)}")

    _linha("OK — pipeline neurossimbólico rodou sobre o currículo USP BCC")


if __name__ == "__main__":
    main()
