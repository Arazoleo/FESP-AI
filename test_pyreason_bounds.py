"""Demo: propagação de bounds de confiança via PyReason.

O KG real do FESP-AI tem todas as arestas PREREQUISITO_DE com confidence=1.0
(ground truth da matriz curricular oficial). Para demonstrar a propagação de
incerteza, este script INJETA artificialmente algumas arestas com confidence
< 1.0 (simulando relações extraídas pelo RelationExtractor a partir de texto
ambíguo) e mostra como o PyReason propaga os bounds através do fecho
transitivo de pré-requisitos.

Cenário:
    A --[1.0]--> B          (prereq sólido, da matriz curricular)
    B --[0.7]--> C          (prereq incerto, extraído de texto)
    C --[1.0]--> D          (prereq sólido)

Resultado esperado do PyReason:
    prereq_trans(A, C) com bound propagado por min([1.0,1], [0.7,1]) = [0.7, 1.0]
    prereq_trans(A, D) com bound = [0.7, 1.0]
    prereq_trans(B, D) com bound = [0.7, 1.0]
"""
import importlib.util
import sys
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _imp(name, path):
    if "src" not in sys.modules:
        pkg = _types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        sys.modules["src"] = pkg
    spec = importlib.util.spec_from_file_location(f"src.{name}", ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules[f"src.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


def banner(t):
    print(f"\n{'='*70}\n{t}\n{'='*70}")


kg_mod = _imp("knowledge_graph", "src/knowledge_graph.py")
nsv_mod = _imp("neurosymbolic_validator", "src/neurosymbolic_validator.py")
pre_mod = _imp("pyreason_engine", "src/pyreason_engine.py")

KnowledgeGraph = kg_mod.KnowledgeGraph
PyReasonEngine = pre_mod.PyReasonEngine

banner("Cenário sintético: propagação de bounds em cadeia")

# KG mínimo de teste
kg = KnowledgeGraph()
g = kg.graph
g.add_node("DISC:A", tipo="disciplina", nome="A")
g.add_node("DISC:B", tipo="disciplina", nome="B")
g.add_node("DISC:C", tipo="disciplina", nome="C")
g.add_node("DISC:D", tipo="disciplina", nome="D")
g.add_edge("DISC:A", "DISC:B", relacao="PREREQUISITO_DE", confidence=1.0)
g.add_edge("DISC:B", "DISC:C", relacao="PREREQUISITO_DE", confidence=0.7)
g.add_edge("DISC:C", "DISC:D", relacao="PREREQUISITO_DE", confidence=1.0)

# Reconstruir índices
kg._index_node("DISC:A", g.nodes["DISC:A"])
kg._index_node("DISC:B", g.nodes["DISC:B"])
kg._index_node("DISC:C", g.nodes["DISC:C"])
kg._index_node("DISC:D", g.nodes["DISC:D"])

print("Arestas iniciais:")
for u, v, d in g.edges(data=True):
    if d.get("relacao") == "PREREQUISITO_DE":
        c = d.get("confidence", 1.0)
        print(f"  {u.replace('DISC:','')} → {v.replace('DISC:','')}  confidence={c}")

eng = PyReasonEngine(kg)
ok = eng._init_reasoner()
print(f"\nPyReason init ok={ok}")

banner("Fecho transitivo com bounds propagados")
for target in ["B", "C", "D"]:
    pairs = eng.get_transitive_prereqs_with_bounds(target)
    print(f"\nprereqs de {target}:")
    for nome, bound in pairs:
        low, high = bound
        marker = "  ← incerteza propagada" if low < 1.0 else ""
        print(f"  {nome:5s} bound=[{low:.0%}, {high:.0%}]{marker}")

banner("Verificação semântica do paper")
# A → D deve propagar 0.7 (mínimo da cadeia)
pairs = eng.get_transitive_prereqs_with_bounds("D")
a_to_d = next(((n, b) for n, b in pairs if n == "A"), None)
print(f"prereq_trans(A, D) = {a_to_d}")
if a_to_d:
    nome, (low, high) = a_to_d
    expected_low = 0.7
    status = "OK" if abs(low - expected_low) < 0.01 else f"DIFF (esperado {expected_low})"
    print(f"  Bound propagado: [{low:.0%}, {high:.0%}]  [{status}]")
    print(f"  Interpretação: 'A é pré-requisito transitivo de D com {low:.0%}–{high:.0%} de confiança'")
    print(f"  Justificativa: cadeia A →[100%] B →[70%] C →[100%] D")
    print(f"  Bound = min de cada elo = 70%")

print("\nDone.")
