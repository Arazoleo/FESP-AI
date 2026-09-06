"""
Testes de regressão da camada APRENDIDA do NSAI (src/rule_miner.py):
mineração de regras, aplicação com crença, ligação conceito↔área, link
prediction de pré-requisito (held-out) e a integração no contexto inferido.

Preserva a tese anti-alucinação: o aprendido nunca sobrescreve fato curado e
sempre entra como sugestão com crença declarada. Executa sem Ollama.
"""

import sys
import importlib.util
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _bootstrap_src_package():
    if "src" not in sys.modules:
        pkg = _types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        pkg.__package__ = "src"
        pkg.__spec__ = importlib.util.spec_from_file_location(
            "src", ROOT / "src/__init__.py",
            submodule_search_locations=[str(ROOT / "src")],
        )
        sys.modules["src"] = pkg


def _import_module(name: str, path: str):
    _bootstrap_src_package()
    full = f"src.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{GREEN}✓{RESET} {desc}")
    else:
        _failed += 1
        print(f"{RED}✗ {desc}{RESET}" + (f" - {detail}" if detail else ""))


kg_mod = _import_module("knowledge_graph", "src/knowledge_graph.py")
rm = _import_module("rule_miner", "src/rule_miner.py")
ns_mod = _import_module("neurosymbolic_validator", "src/neurosymbolic_validator.py")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)

print(f"\n{BOLD}── mineração de regras ──{RESET}")
regras = rm.minerar_regras(kg, min_support=5, min_conf=0.15, min_body=10)
check("minera ao menos uma regra Horn", len(regras) >= 1, str(len(regras)))
check("toda regra tem confidence em (0,1] e support>0",
      all(0 < g["confidence"] <= 1 and g["support"] > 0 for g in regras))
check("regras ordenadas por confiança desc",
      regras == sorted(regras, key=lambda g: (-g["confidence"], -g["support"])))

print(f"\n{BOLD}── aplicação com crença (forward-chaining) ──{RESET}")
inf = rm.aplicar_regras(kg, regras, min_conf=0.3)
check("deriva relações inferidas", len(inf) > 0, str(len(inf)))
check("crença de toda inferência ≤ 1", all(d["crenca"] <= 1.0 for d in inf))
curadas = {(u, v) for u, v, d in kg.graph.edges(data=True)
           if d.get("relacao") == "REQUER_BASE"}
node_by_name = {kg.graph.nodes[n].get("nome"): n for n in kg.graph.nodes}
check("inferência NÃO duplica fato curado (não sobrescreve verdade)",
      all((d["sujeito"], d["objeto"]) not in curadas for d in inf
          if d["cabeca"] == "REQUER_BASE"))

print(f"\n{BOLD}── ligação conceito → área (fecha a lacuna) ──{RESET}")
pa = rm.ligar_conceito_area(kg, min_evidencia=2)
check("deriva ligações conceito→área", len(pa) > 10, str(len(pa)))
check("toda ligação tem crença em (0,1]", all(0 < d["crenca"] <= 1 for d in pa))

print(f"\n{BOLD}── link prediction de pré-requisito (held-out) ──{RESET}")
res = rm.avaliar_prereq_holdout(kg, n_folds=5)
check("recall@10 forte (sinal conceitual prediz pré-requisito)",
      res["recall@10"] >= 0.5, f"recall@10={res['recall@10']}")
check("recall cresce com k (monotônico)",
      res["recall@1"] <= res["recall@3"] <= res["recall@5"] <= res["recall@10"])
check("MRR positivo", res["mrr"] > 0.2, str(res["mrr"]))

print(f"\n{BOLD}── sugestão de pré-requisitos (política de crença) ──{RESET}")
sug = rm.sugerir_prereqs(kg, "Compiladores", top_k=3)
check("sugere pré-requisitos prováveis para Compiladores", len(sug) >= 1, str(sug))
prereq_curados = {a for (a, b) in
                  {(u, v) for u, v, d in kg.graph.edges(data=True)
                   if d.get("relacao") == "PREREQUISITO_DE"}
                  if b == kg._find_node("Compiladores", "disciplina")}
nomes_curados = {kg.graph.nodes[a].get("nome") for a in prereq_curados}
check("sugestão NÃO inclui pré-requisito já curado",
      all(s["candidato"] not in nomes_curados for s in sug),
      f"curados={nomes_curados}")

print(f"\n{BOLD}── integração no contexto inferido ──{RESET}")
engine = ns_mod.InferenceEngine(kg)
ctx = engine.derive_facts_for_context("prerequisite_chain", "Compiladores")
check("contexto inferido inclui a camada learned_prereq",
      "learned_prereq" in ctx, ctx[:80])
check("aprendido é marcado como SUGESTÃO/não-curado (preserva a tese)",
      "SUGESTÃO" in ctx and "NÃO curado" in ctx)
check("a crença aparece declarada (formato ~N%)",
      "~" in ctx and "%" in ctx)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
