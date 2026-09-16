"""
Mini-benchmark simbólico do currículo USP BCC (replicação p/ o paper CTIC).

Respostas de referência calculadas À MÃO a partir dos dados OFICIAIS do
JupiterWeb (curso_usp_bcc.json) e comparadas com a saída das regras R1-R5 do
MESMO motor da graduação. Mede se o framework neurossimbólico, sem qualquer
mudança no motor, reproduz a verdade curricular de um segundo currículo.

Roda no container. Uso: python replicacao_usp/benchmark_usp.py
"""

import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_graph import KnowledgeGraph
from src.neurosymbolic_validator import _build_default_engine


def _norm_set(kg, nomes):
    return {kg._normalize_text(n) for n in nomes}


def main():
    kg = KnowledgeGraph()
    for md in sorted(Path(os.path.join(ROOT, "markdown_usp_bcc")).glob("*.md")):
        kg._process_discipline_file(md)
    engine = _build_default_engine(kg)

    ok = 0
    total = 0
    falhas = []

    def check(nome, obtido, esperado):
        nonlocal ok, total
        total += 1
        passou = _norm_set(kg, obtido) == _norm_set(kg, esperado)
        if passou:
            ok += 1
        else:
            falhas.append((nome, sorted(obtido), sorted(esperado)))
        print(f"  {'✓' if passou else '✗'} {nome}")

    print("== R1: fecho transitivo de pré-requisitos ==")
    check("trans(Análise de Algoritmos)",
          kg.get_all_ancestors("Análise de Algoritmos"),
          ["Introdução à Computação", "Algoritmos e Estruturas de Dados I",
           "Algoritmos e Estruturas de Dados II"])
    check("trans(Sistemas Operacionais)",
          kg.get_all_ancestors("Sistemas Operacionais"),
          ["Introdução à Computação", "Algoritmos e Estruturas de Dados I",
           "Algoritmos e Estruturas de Dados II"])
    check("trans(Funções Diferenciáveis e Séries)",
          kg.get_all_ancestors("Funções Diferenciáveis e Séries"),
          ["Cálculo Diferencial e Integral I", "Cálculo Diferencial e Integral II"])
    check("trans(Laboratório de Métodos Numéricos)",
          kg.get_all_ancestors("Laboratório de Métodos Numéricos"),
          ["Introdução à Computação", "Vetores e Geometria", "Álgebra Linear I"])

    print("== R3: disciplinas críticas (θ=2) ==")
    criticas = {n for n, _ in engine.critical_disciplines(min_dependents=2)}
    check("críticas(θ=2)", criticas,
          ["Introdução à Computação", "Algoritmos e Estruturas de Dados I",
           "Algoritmos e Estruturas de Dados II"])

    print("== R4: co-pré-requisitos ==")
    check("co-prereq(Álgebra Linear I)",
          engine.find_co_prerequisites("Álgebra Linear I"),
          ["Introdução à Computação", "Vetores e Geometria"])
    check("co-prereq(Introdução à Computação)",
          engine.find_co_prerequisites("Introdução à Computação"),
          ["Vetores e Geometria", "Álgebra Linear I"])

    print("== R2: desbloqueio dado conjunto cursado ==")
    unlocked = engine.derive_unlocked(
        ["Introdução à Computação", "Cálculo Diferencial e Integral I",
         "Vetores e Geometria"])
    check("unlocked(1º semestre)", unlocked,
          ["Algoritmos e Estruturas de Dados I", "Cálculo Diferencial e Integral II",
           "Lógica e Verificação de Programas", "Modelagem e Simulação",
           "Técnicas de Programação I", "Álgebra Linear I"])

    print("== R5: plano mínimo (fases achatadas) ==")
    plano = engine.plan_minimal_path("Análise de Algoritmos", []) or []
    flat = [d for fase in plano for d in fase]
    check("plano(Análise de Algoritmos)", flat,
          ["Introdução à Computação", "Algoritmos e Estruturas de Dados I",
           "Algoritmos e Estruturas de Dados II", "Análise de Algoritmos"])

    print("== pré-requisito direto (consulta ao KG) ==")
    check("prereq-direto(AED II)",
          kg.get_direct_prerequisites("Algoritmos e Estruturas de Dados II"),
          ["Algoritmos e Estruturas de Dados I"])
    check("prereq-direto(Cálculo II)",
          kg.get_direct_prerequisites("Cálculo Diferencial e Integral II"),
          ["Cálculo Diferencial e Integral I"])
    check("prereq-direto(Laboratório de Métodos Numéricos)",
          kg.get_direct_prerequisites("Laboratório de Métodos Numéricos"),
          ["Álgebra Linear I", "Introdução à Computação"])

    print("\n" + "=" * 60)
    print(f"Verificação simbólica no currículo USP BCC: {ok}/{total} corretos")
    print("=" * 60)
    for nome, obt, esp in falhas:
        print(f"  FALHA {nome}\n    obtido={obt}\n    esperado={esp}")


if __name__ == "__main__":
    main()
