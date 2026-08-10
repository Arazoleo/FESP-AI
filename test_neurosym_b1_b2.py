"""
Testes de regressão das melhorias B1 (reescrita corretiva genérica) e
B2 (propagação de incerteza no caminho mínimo) do roadmap neurossimbólico.

Executa sem Ollama: o B1 usa um LLM fake local.
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
    full_name = f"src.{name}"
    spec = importlib.util.spec_from_file_location(full_name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules[full_name] = mod
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
ns_mod = _import_module("neurosymbolic_validator", "src/neurosymbolic_validator.py")
gr_mod = _import_module("graph_rag", "src/graph_rag.py")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)

engine = ns_mod.InferenceEngine(kg)

print(f"\n{BOLD}── B2: path_confidence ──{RESET}")
phases = engine.plan_minimal_path("Compiladores", [])
check("caminho para Compiladores existe", phases is not None and len(phases) > 1)

per_disc, bound = engine.path_confidence(phases)
check(
    "com arestas em confiança 1.0, bound do caminho é 1.0",
    bound == 1.0 and not per_disc,
    f"bound={bound}, per_disc={per_disc}",
)

lfa = "Linguagens Formais e Autômatos"
comp_id = kg._find_node("Compiladores", "disciplina")
lfa_id = kg._find_node(lfa, "disciplina")
edge_data = kg.graph.get_edge_data(lfa_id, comp_id)
edge_key = next(
    k for k, e in edge_data.items() if e.get("relacao") == "PREREQUISITO_DE"
)
kg.graph[lfa_id][comp_id][edge_key]["confidence"] = 0.7

per_disc, bound = engine.path_confidence(phases)
check(
    "aresta com confiança 0.7 rebaixa o bound do caminho para 0.7",
    abs(bound - 0.7) < 1e-9,
    f"bound={bound}",
)
check(
    "a disciplina habilitada pelo elo fraco é anotada individualmente",
    abs(per_disc.get("Compiladores", 0) - 0.7) < 1e-9,
    f"per_disc={per_disc}",
)

graph_engine = gr_mod.GraphRAGEngine(kg)
resposta = graph_engine.query_graph("trajectory_planning", "compiladores")
check(
    "resposta do trajectory_planning anota a confiança parcial",
    "confiança 70%" in resposta,
    resposta.splitlines()[-1] if resposta else "(None)",
)
check(
    "resposta inclui o bound inferior do caminho",
    "bound inferior" in resposta.lower() and "70%" in resposta,
)

ctx = engine._infer_trajectory_context("compiladores")
check(
    "fatos inferidos para o LLM incluem o bound de incerteza",
    "incerteza" in ctx.lower() and "70%" in ctx,
    ctx,
)

kg.graph[lfa_id][comp_id][edge_key]["confidence"] = 1.0

print(f"\n{BOLD}── B1: validação genérica detecta disciplina inexistente ──{RESET}")
validator = ns_mod.SymbolicValidator(kg)

resp_ok = "A disciplina Compiladores aborda análise léxica e sintática."
v = validator.validate_response(resp_ok, "ementa_disciplina", "compiladores")
check("disciplina real não gera violação", not v.violations, str(v.violations))

resp_bad = "Recomendo cursar a disciplina Alquimia Computacional Avançada, que é ótima."
v = validator.validate_response(resp_bad, "ementa_disciplina", "compiladores")
check(
    "disciplina inventada gera violação",
    any("Alquimia" in viol for viol in v.violations),
    str(v.violations),
)

frase_generica = "Essa é uma disciplina de graduação com foco em teoria."
v = validator.validate_response(frase_generica, "ementa_disciplina", "compiladores")
check(
    "frase genérica ('disciplina de graduação') não gera falso positivo",
    not v.violations,
    str(v.violations),
)

print(f"\n{BOLD}── B1: reescrita corretiva genérica ──{RESET}")

final, v = validator.validate_and_correct(resp_bad, "ementa_disciplina", "compiladores")
check(
    "sem LLM, resposta não é reescrita (só anotada)",
    not v.was_corrected and resp_bad in final,
)


try:
    import langchain_core.messages
except ImportError:
    lc = _types.ModuleType("langchain_core")
    lc_msgs = _types.ModuleType("langchain_core.messages")

    class _HumanMessage:
        def __init__(self, content):
            self.content = content

    lc_msgs.HumanMessage = _HumanMessage
    lc.messages = lc_msgs
    sys.modules.setdefault("langchain_core", lc)
    sys.modules["langchain_core.messages"] = lc_msgs


class FakeLLM:
    """Simula o LLM devolvendo uma reescrita fixa."""
    def invoke(self, messages):
        class R:
            content = "Compiladores aborda análise léxica, sintática e geração de código."
        return R()


validator_llm = ns_mod.SymbolicValidator(kg, llm=FakeLLM())
final, v = validator_llm.validate_and_correct(resp_bad, "ementa_disciplina", "compiladores")
check(
    "com LLM, resposta com violação é reescrita (was_corrected=True)",
    v.was_corrected and "Alquimia" not in final.split("\n")[0],
    f"was_corrected={v.was_corrected}",
)
check(
    "regra generic_kg_rewrite registrada",
    "generic_kg_rewrite" in v.inference_rules_applied,
    str(v.inference_rules_applied),
)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
