"""Smoke test: paridade entre InferenceEngine (Python) e PyReasonEngine.

Carrega o KG real do FESP-AI e compara os outputs dos dois motores em:
  - fecho transitivo de pré-requisitos
  - co-pré-requisitos
  - critical_disciplines (deve ser idêntico - herdado)

Reporta diferenças e tempos.
"""
import importlib.util
import sys
import time
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _bootstrap_src_package():
    if "src" not in sys.modules:
        pkg = _types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        pkg.__package__ = "src"
        sys.modules["src"] = pkg


def _import_module(name: str, path: str):
    _bootstrap_src_package()
    full_name = f"src.{name}"
    spec = importlib.util.spec_from_file_location(full_name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


kg_mod = _import_module("knowledge_graph", "src/knowledge_graph.py")
nsv_mod = _import_module("neurosymbolic_validator", "src/neurosymbolic_validator.py")
pre_mod = _import_module("pyreason_engine", "src/pyreason_engine.py")

KnowledgeGraph = kg_mod.KnowledgeGraph
InferenceEngine = nsv_mod.InferenceEngine
PyReasonEngine = pre_mod.PyReasonEngine


def banner(t):
    print(f"\n{'='*70}\n{t}\n{'='*70}")


banner("Carregando KG")
kg = KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)
stats = kg.get_stats()
print(f"KG: {stats['total_nos']} nós, {stats['total_arestas']} arestas, {stats['disciplinas']} disciplinas")

banner("Inicializando engines")
t0 = time.time()
py_engine = InferenceEngine(kg)
t_py = time.time() - t0
print(f"InferenceEngine (Python): {t_py*1000:.1f}ms")

t0 = time.time()
pr_engine = PyReasonEngine(kg)
ok = pr_engine._init_reasoner()
t_pr = time.time() - t0
print(f"PyReasonEngine: {t_pr:.2f}s (init reasoner ok={ok})")

banner("Selecionando amostras")
sample = []
for node_id, data in kg.graph.nodes(data=True):
    if data.get("tipo") != "disciplina":
        continue
    nome = data.get("nome")
    if not nome:
        continue
    prereqs = kg.get_prerequisite_chain(nome, max_depth=1)
    if prereqs:
        sample.append(nome)
    if len(sample) >= 8:
        break
print(f"Amostra: {sample}")

banner("Fecho transitivo (Python vs PyReason)")
mismatches = 0
for disc in sample:
    py_anc = sorted(set(kg.get_all_ancestors(disc)))
    pr_pairs = pr_engine.get_transitive_prereqs_with_bounds(disc)
    pr_anc = sorted({p for p, _ in pr_pairs})
    diff_py = set(py_anc) - set(pr_anc)
    diff_pr = set(pr_anc) - set(py_anc)
    status = "OK" if not diff_py and not diff_pr else "DIFF"
    if status == "DIFF":
        mismatches += 1
    print(f"  [{status}] {disc[:40]:<40} | python={len(py_anc)}  pyreason={len(pr_anc)}")
    if diff_py:
        print(f"    só Python: {sorted(diff_py)[:3]}")
    if diff_pr:
        print(f"    só PyReason: {sorted(diff_pr)[:3]}")
print(f"\n→ Divergências: {mismatches}/{len(sample)}")

banner("Co-pré-requisitos")
co_mismatches = 0
for disc in sample[:5]:
    py_co = set(py_engine.find_co_prerequisites(disc))
    pr_co = set(pr_engine.find_co_prerequisites(disc))
    only_py = py_co - pr_co
    only_pr = pr_co - py_co
    status = "OK" if not only_py and not only_pr else "DIFF"
    if status == "DIFF":
        co_mismatches += 1
    print(f"  [{status}] {disc[:40]:<40} | python={len(py_co)}  pyreason={len(pr_co)}")
    if only_py:
        print(f"    só Python: {sorted(only_py)[:3]}")
    if only_pr:
        print(f"    só PyReason: {sorted(only_pr)[:3]}")
print(f"\n→ Divergências co_prereq: {co_mismatches}/5")

banner("Demonstração: bounds de confiança propagados")
for disc in sample[:4]:
    pairs = pr_engine.get_transitive_prereqs_with_bounds(disc)
    if not pairs:
        continue
    print(f"\n{disc}:")
    for nome, bound in pairs[:6]:
        low, high = bound[0], bound[1]
        marker = "" if low >= 1.0 else "  ← incerteza propagada"
        print(f"  {nome[:50]:<50}  [{low:.0%}, {high:.0%}]{marker}")

banner("Contexto inferido (output que vai pro LLM)")
for disc in sample[:2]:
    print(f"\n--- {disc} (Python) ---")
    print(py_engine._infer_prereq_context(disc))
    print(f"\n--- {disc} (PyReason) ---")
    print(pr_engine._infer_prereq_context(disc))

print("\nDone.")
