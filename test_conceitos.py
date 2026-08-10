"""
Testes da camada de conceitos (regra R6, base recomendada por conceito).

Constrói o Knowledge Graph real a partir dos markdowns e verifica:
- aterramento do seed (nomes que não resolvem são descartados, sem nó fantasma)
- isolamento: nós de conceito fora dos índices de disciplina (sem colisão)
- regra R6 no caso real: IA pressupõe probabilidade/estatística/álgebra linear
- exclusão de ancestrais formais e respeito à ordem dos termos

Executa sem LLM/backend.
"""

import importlib.util
import sys
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

if "src" not in sys.modules:
    _pkg = _types.ModuleType("src")
    _pkg.__path__ = [str(ROOT / "src")]
    _pkg.__package__ = "src"
    sys.modules["src"] = _pkg
_spec = importlib.util.spec_from_file_location(
    "src.knowledge_graph", ROOT / "src/knowledge_graph.py"
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "src"
sys.modules["src.knowledge_graph"] = _mod
_spec.loader.exec_module(_mod)
KnowledgeGraph = _mod.KnowledgeGraph

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  {GREEN}PASS{RESET} {desc}")
    else:
        _failed += 1
        print(f"  {RED}FAIL{RESET} {desc}" + (f" - {detail}" if detail else ""))


print(f"\n{BOLD}Construindo o KG real (markdowns){RESET}")
kg = KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir=str(ROOT / "markdown_disciplinas"),
    regimentos_dir=str(ROOT / "markdown_regimentos"),
    docentes_dir=str(ROOT / "markdown_docentes"),
    cursos_dir=str(ROOT / "markdown_cursos"),
)

conceitos = [n for n, d in kg.graph.nodes(data=True) if d.get("tipo") == "conceito"]
arestas_aborda = [
    (u, v) for u, v, d in kg.graph.edges(data=True) if d.get("relacao") == "ABORDA"
]
arestas_requer = [
    (u, v) for u, v, d in kg.graph.edges(data=True) if d.get("relacao") == "REQUER_BASE"
]

print(f"\n{BOLD}1. Carga do seed com aterramento{RESET}")
check("conceitos criados", len(conceitos) > 0, str(len(conceitos)))
check("arestas ABORDA criadas", len(arestas_aborda) > 0, str(len(arestas_aborda)))
check("arestas REQUER_BASE criadas", len(arestas_requer) > 0, str(len(arestas_requer)))
check(
    "todo conceito usa namespace CONC:",
    all(n.startswith("CONC:") for n in conceitos),
)
check(
    "toda aresta de conceito parte de disciplina real",
    all(
        kg.graph.nodes[u].get("tipo") == "disciplina"
        for u, _ in arestas_aborda + arestas_requer
    ),
)

print(f"\n{BOLD}2. Isolamento dos índices (sem poluição){RESET}")
disc_alg = kg._find_node("Álgebra Linear", "disciplina")
check(
    "'Álgebra Linear' resolve para a DISCIPLINA, não para o conceito homônimo",
    disc_alg is not None
    and kg.graph.nodes[disc_alg].get("tipo") == "disciplina"
    and not disc_alg.startswith("CONC:"),
    str(disc_alg),
)
indices = list(kg._index_by_name.values()) + list(kg._index_by_sigla.values())
check(
    "nenhum nó de conceito entrou nos índices de nome/sigla",
    not any(str(v).startswith("CONC:") for v in indices),
)

print(f"\n{BOLD}3. Regra R6: caso real (IA pressupõe prob/est/álgebra){RESET}")
base_ia = kg.get_base_recomendada("Inteligência Artificial")
nomes_base = {b["nome"] for b in base_ia}
check(
    "Probabilidade e Estatística recomendada antes de IA",
    any("Probabilidade" in n for n in nomes_base),
    str(nomes_base),
)
check(
    "Álgebra Linear recomendada antes de IA",
    any("Álgebra Linear" in n for n in nomes_base),
    str(nomes_base),
)
check(
    "confiança propagada em [0, 1]",
    all(0 < b["confidence"] <= 1 for b in base_ia),
)
check(
    "conceitos mediadores expostos na resposta",
    all(b["conceitos"] for b in base_ia),
)

print(f"\n{BOLD}4. Exclusões da regra{RESET}")
prereqs_formais = set(kg.get_prerequisite_chain("Inteligência Artificial") or [])
check(
    "nenhum pré-requisito FORMAL de IA aparece na base recomendada",
    not (nomes_base & prereqs_formais),
    str(nomes_base & prereqs_formais),
)
check(
    "disciplina sem REQUER_BASE retorna lista vazia",
    kg.get_base_recomendada("Teoria dos Grafos") == [],
)
check(
    "disciplina inexistente retorna lista vazia",
    kg.get_base_recomendada("Disciplina Que Nao Existe XYZ") == [],
)

print(f"\n{BOLD}5. Consultas auxiliares{RESET}")
check(
    "conceitos abordados por Probabilidade e Estatística",
    set(kg.get_conceitos_abordados("Probabilidade e Estatística"))
    >= {"probabilidade", "estatística"},
    str(kg.get_conceitos_abordados("Probabilidade e Estatística")),
)
req_ia = {r["conceito"] for r in kg.get_conceitos_requeridos("Inteligência Artificial")}
check(
    "conceitos requeridos por IA",
    req_ia >= {"probabilidade", "estatística", "álgebra linear"},
    str(req_ia),
)

print(f"\n{BOLD}6. Seed com nomes que não resolvem não cria nó fantasma{RESET}")
import json as _json
import tempfile, os
seed_fake = {
    "aborda": {"conceito teste xyz": ["Disciplina Inexistente ABC"]},
    "requer_base": {"Outra Inexistente DEF": {"conceito teste xyz": 1.0}},
}
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    _json.dump(seed_fake, f, ensure_ascii=False)
    fake_path = f.name
antes_nos = kg.graph.number_of_nodes()
stats = kg.load_conceitos(fake_path)
os.unlink(fake_path)
check("todas as entradas inválidas ignoradas", stats["ignorados"] == 2, str(stats))
check("nenhuma aresta criada", stats["aborda"] == 0 and stats["requer_base"] == 0)
check("nenhum nó novo criado", kg.graph.number_of_nodes() == antes_nos)

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
