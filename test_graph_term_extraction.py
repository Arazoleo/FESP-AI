"""
Testes de regressão da extração de termo do GraphRAG.

Cobre as falhas registradas nas transcrições do BACKLOG.md:
  - "Quero chegar em Compiladores. Por onde começo?" roteava para matriz_info
    (o pega-tudo casava com o "de" dentro de "onde") com termo "começo".
  - "Para cursar Compiladores, preciso ter feito quais disciplinas no total?"
    extraía o termo-lixo "feito disciplinas total".
  - "Como chegar em Banco de Dados?" caía em matriz_info via "de Dados".

Executa sem precisar de Ollama/LLM (usa apenas o fallback regex + KG).
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


def check(desc: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{GREEN}✓{RESET} {desc}")
    else:
        _failed += 1
        print(f"{RED}✗ {desc}{RESET}" + (f" — {detail}" if detail else ""))


kg_mod = _import_module("knowledge_graph", "src/knowledge_graph.py")
gr_mod = _import_module("graph_rag", "src/graph_rag.py")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)
engine = gr_mod.GraphRAGEngine(kg)

print(f"\n{BOLD}── graph_patterns disponível sem set_llm ──{RESET}")
check(
    "graph_patterns existe logo após o construtor",
    hasattr(engine, "graph_patterns") and bool(engine.graph_patterns),
)

print(f"\n{BOLD}── Roteamento e extração (fallback regex) ──{RESET}")
CASES = [
    # (pergunta, intent esperado, termo esperado — None ignora)
    ("Quero chegar em Compiladores. Por onde começo?", "trajectory_planning", "compiladores"),
    ("Quero chegar em Compiladores", "trajectory_planning", "compiladores"),
    ("Quero chegar em Compiladores, já fiz Matemática Discreta",
     "trajectory_planning", "matemática discreta:compiladores"),
    ("Já cursei Cálculo 1, AED I: como chego em Compiladores?",
     "trajectory_planning", "cálculo 1, aed i:compiladores"),
    ("Como chegar em Banco de Dados?", "trajectory_planning", "banco de dados"),
    ("Para cursar Compiladores, preciso ter feito quais disciplinas no total?",
     "prerequisite_chain", "Compiladores"),
    ("Quais os pré-requisitos de Compiladores?", "prerequisite_chain", "compiladores"),
]
for question, exp_intent, exp_term in CASES:
    use, intent, term = engine.should_use_graph(question)
    check(
        f"{question!r} → {exp_intent}/{exp_term}",
        use and intent == exp_intent and (exp_term is None or term == exp_term),
        f"obteve intent={intent!r} term={term!r}",
    )

print(f"\n{BOLD}── Resposta fim-a-fim no grafo ──{RESET}")
E2E = [
    ("Quero chegar em Compiladores. Por onde começo?", "Caminho mínimo para Compiladores"),
    ("Quero chegar em Compiladores, já fiz Matemática Discreta", "Caminho mínimo para Compiladores"),
    ("Como chegar em Banco de Dados?", "Caminho mínimo para Banco de Dados"),
    ("Para cursar Compiladores, preciso ter feito quais disciplinas no total?",
     "Cadeia de pré-requisitos de Compiladores"),
]
for question, expected_snippet in E2E:
    use, intent, term = engine.should_use_graph(question)
    answer = engine.query_graph(intent, term) if use else None
    check(
        f"{question!r} responde com {expected_snippet!r}",
        answer is not None and expected_snippet in answer,
        f"resposta: {(answer or '(None)').splitlines()[0]!r}",
    )

print(f"\n{BOLD}── Grounding de termo-lixo no KG ──{RESET}")
check(
    "termo-lixo 'feito disciplinas total' aterra para 'Compiladores' via pergunta",
    engine._ground_discipline_term(
        "Para cursar Compiladores, preciso ter feito quais disciplinas no total?",
        "prerequisite_chain", "feito disciplinas total",
    ) == "Compiladores",
)
check(
    "termo válido não é alterado pelo grounding",
    engine._ground_discipline_term(
        "Quais os pré-requisitos de Compiladores?", "prerequisite_chain", "compiladores",
    ) == "compiladores",
)
check(
    "formato 'cursadas:' (sem alvo) é preservado",
    engine._ground_discipline_term(
        "Já fiz Cálculo 1, como fica?", "trajectory_planning", "cálculo 1:",
    ) == "cálculo 1:",
)
check(
    "alvo irreconhecível gera pedido de clarificação, não eco de lixo",
    "identificar a disciplina alvo" in (
        engine.query_graph("trajectory_planning", "xyz inexistente qualquer") or ""
    ),
)

print(f"\n{BOLD}── Grounding de termo de CURSO ──{RESET}")
check(
    "'Quais as eletivas de BCC?' extrai o curso",
    engine.should_use_graph("Quais as eletivas de BCC?")[1:] == ("eletivas_curso", "bcc"),
    str(engine.should_use_graph("Quais as eletivas de BCC?")),
)
check(
    "termo-lixo sem curso → pedido de clarificação (não eco)",
    "qual curso" in engine.query_graph("eletivas_curso", "algumas dessas eletivas").lower(),
)
check(
    "termo-lixo contendo curso aterra e responde",
    "BCT" in engine.query_graph("eletivas_curso", "algumas dessas eletivas do bct"),
)
check(
    "_find_curso_in_text acha curso por sigla",
    "Ciência da Computação" in engine._find_curso_in_text("eletivas do bcc por favor"),
    engine._find_curso_in_text("eletivas do bcc por favor"),
)

print(f"\n{BOLD}── critical_disciplines: filtro de curso e dedup ──{RESET}")
crit_bcc = engine.query_graph("critical_disciplines", "bcc")
check(
    "filtro por BCC não vaza disciplinas de outros cursos",
    "BCC" in crit_bcc and not any(x in crit_bcc for x in ("Fisiologia", "Materiais Polim")),
)
crit_global = engine.query_graph("critical_disciplines", "")
check(
    "modo global avisa o escopo e sugere filtrar por curso",
    "todos os cursos" in crit_global,
)
check(
    "variantes duplicadas do KG são deduplicadas",
    crit_global.count("Biologia Moderna") <= 1,
)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
