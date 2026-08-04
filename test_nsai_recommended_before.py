"""
Testes da inferência de disciplinas RECOMENDADAS ANTES (regra recommended_before).

Regra (KGCompletion.get_recommended_before / InferenceEngine.RULES):
  recommended_before(A,B) ⟺ sim_ementa(A,B) ≥ θ ∧ ¬ancestral(A,B)
                            ∧ ¬ancestral(B,A) ∧ ordem(A) < ordem(B)

Cobre:
  - Enriquecimento do nó com a ementa no build (_process_discipline_file)
  - Graceful sem embeddings (lista vazia, respostas simbólicas intactas)
  - Filtros simbólicos: pares na MESMA cadeia do DAG nunca aparecem
    (ex.: Lógica de Programação × Compiladores) e a direção respeita ordem()
  - Par real calibrado: Arquitetura e Organização de Computadores →
    Sistemas Operacionais (sim 0.68 com embeddinggemma; aqui simulado com
    um modelo fake determinístico — a similaridade real foi validada na
    calibração de θ)
  - Intent recommended_before ("o que é bom fazer antes de X?") sem roubar
    "o que preciso fazer antes de X" (prerequisite_chain)
  - query_graph + graph_payload (arestas inferidas com flag `inferida`)

Executa sem precisar de Ollama/LLM.
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
ic_mod = _import_module("intent_classifier", "src/intent_classifier.py")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)
engine = gr_mod.GraphRAGEngine(kg)

SO = "Sistemas Operacionais"
AOC = "Arquitetura e Organização de Computadores"

print(f"\n{BOLD}── Enriquecimento do nó com a ementa (build) ──{RESET}")
paa_id = kg._find_node("PAA", "disciplina")
paa_ementa = kg.graph.nodes.get(paa_id, {}).get("ementa", "")
check(
    "nó de PAA tem ementa não-vazia e truncada a 800 chars",
    bool(paa_ementa) and "assintótica" in paa_ementa and len(paa_ementa) <= 800,
    paa_ementa[:60],
)
lfa_id = kg._find_node("LFA", "disciplina")
check(
    "nó de LFA tem ementa (Autômatos)",
    "utômatos" in kg.graph.nodes.get(lfa_id, {}).get("ementa", ""),
)

print(f"\n{BOLD}── Graceful sem embeddings ──{RESET}")
check(
    "get_recommended_before sem embeddings → lista vazia",
    kg.kgc.get_recommended_before("PAA") == [],
)
resp_sem_emb = engine.query_graph("recommended_before", "paa") or ""
check(
    "query_graph recommended_before sem embeddings → mensagem honesta, sem crash",
    "conteúdo suficientemente próximo" in resp_sem_emb,
    resp_sem_emb[:80],
)
resp_prereq = engine.query_graph("prerequisite_chain", "compiladores") or ""
check(
    "prerequisite_chain sem embeddings segue intacta (sem seção inferida)",
    "Cadeia de pré-requisitos de Compiladores" in resp_prereq
    and "Recomendadas antes" not in resp_prereq,
)

print(f"\n{BOLD}── Filtros simbólicos (modelo fake: sim=1 para todo par) ──{RESET}")


class FakeAllEqual:
    """Todo doc vira o mesmo vetor → sim=1.0 para qualquer par.

    Isola os filtros SIMBÓLICOS: tudo que sobreviver passou apenas por
    ¬ancestral ∧ ordem(A) < ordem(B)."""

    def embed_documents(self, docs):
        return [[1.0, 1.0] for _ in docs]

    def embed_query(self, q):
        return [1.0, 1.0]


kg.kgc.set_embeddings(FakeAllEqual())
kg.kgc.invalidate_cache()

recs_comp = kg.kgc.get_recommended_before("Compiladores", n=10_000)
nomes_comp = {n for n, _ in recs_comp}
check("com sim=1 universal, Compiladores recebe candidatos", bool(recs_comp))
check(
    "pares na MESMA cadeia nunca aparecem: ancestrais de Compiladores "
    "(LFA, Matemática Discreta, Lógica de Programação) excluídos",
    not nomes_comp & {
        "Linguagens Formais e Autômatos", "Matemática Discreta",
        "Lógica de Programação",
    },
    str(nomes_comp & {
        "Linguagens Formais e Autômatos", "Matemática Discreta",
        "Lógica de Programação",
    }),
)
recs_logica = kg.kgc.get_recommended_before("Lógica de Programação", n=10_000)
check(
    "descendentes também excluídos: Compiladores nunca é recomendada "
    "antes de Lógica de Programação",
    "Compiladores" not in {n for n, _ in recs_logica},
)

# Direção: ordem(A) < ordem(B) para todo par retornado
paa_data = kg.graph.nodes[paa_id]
recs_paa = kg.kgc.get_recommended_before("PAA", n=10_000)
direcao_ok = True
for nome_a, _ in recs_paa:
    nid = kg._find_node(nome_a, "disciplina")
    oa, ob = kg.kgc._ordem_pair(kg.graph.nodes[nid], paa_data)
    if oa >= ob:
        direcao_ok = False
        break
check(
    "direção respeita ordem(A) < ordem(B) em TODOS os pares de PAA",
    bool(recs_paa) and direcao_ok,
)
check(
    "LFA (termo 5) nunca é recomendada antes de PAA (termo 4) — direção",
    "Linguagens Formais e Autômatos" not in {n for n, _ in recs_paa},
)
check(
    "confidence sempre < 1.0 (aresta inferida, aparece tracejada)",
    all(0 < s < 1.0 for _, s in recs_paa),
)

print(f"\n{BOLD}── Conjunção semântico-simbólica (modelo fake por palavra-chave) ──{RESET}")


class FakeKeyword:
    """Vetor [1,0] p/ docs de SO/Arquitetura; [0,1] p/ o resto → só o par
    SO×AOC tem sim ≥ θ (simula o par real da calibração: sim 0.68)."""

    def _vec(self, doc):
        if "Arquitetura e Organização de Computadores" in doc or \
                doc.startswith("Sistemas Operacionais"):
            return [1.0, 0.0]
        return [0.0, 1.0]

    def embed_documents(self, docs):
        return [self._vec(d) for d in docs]

    def embed_query(self, q):
        return self._vec(q)


kg.kgc.set_embeddings(FakeKeyword())
kg.kgc.invalidate_cache()

recs_so = kg.kgc.get_recommended_before(SO, n=5)
nomes_so = {n for n, _ in recs_so}
check(
    f"'{AOC}' aparece nas recomendadas de '{SO}'",
    AOC in nomes_so,
    str(nomes_so),
)
check(
    "disciplinas sem sobreposição de conteúdo ficam fora (sim < θ)",
    "Bioquímica" not in nomes_so and "Cálculo I" not in nomes_so,
)

print(f"\n{BOLD}── Intent recommended_before (fallback regex, sem LLM) ──{RESET}")
CASES = [
    ("O que é bom fazer antes de PAA?", "recommended_before", "paa"),
    ("O que ajuda a fazer antes de Compiladores?", "recommended_before", "compiladores"),
    ("Quais disciplinas são recomendadas antes de Banco de Dados?",
     "recommended_before", "banco de dados"),
    # NÃO pode roubar prerequisite_chain:
    ("O que preciso fazer antes de PAA?", "prerequisite_chain", None),
    ("Quais os pré-requisitos de PAA?", "prerequisite_chain", "paa"),
    ("O que devo cursar antes de Compiladores?", "prerequisite_chain", None),
]
for question, exp_intent, exp_term in CASES:
    use, intent, term = engine.should_use_graph(question)
    check(
        f"{question!r} → {exp_intent}",
        use and intent == exp_intent and (exp_term is None or term == exp_term),
        f"obteve intent={intent!r} term={term!r}",
    )

quick = ic_mod.IntentClassifier()._quick_regex_check
check(
    "QUICK_PATTERNS: 'o que é bom fazer antes de paa?' → recommended_before "
    "(vence o 'o que é' da ementa)",
    quick("o que é bom fazer antes de paa?") == "recommended_before",
    str(quick("o que é bom fazer antes de paa?")),
)
check(
    "QUICK_PATTERNS: 'o que preciso fazer antes de paa?' NÃO é recommended_before",
    quick("o que preciso fazer antes de paa?") != "recommended_before",
    str(quick("o que preciso fazer antes de paa?")),
)

print(f"\n{BOLD}── SYMBOLIC_DIRECT_INTENTS e RULES ──{RESET}")
router_mod = _import_module("workflow.router_test", "src/workflow/router.py")
check(
    "recommended_before está em SYMBOLIC_DIRECT_INTENTS (atalho simbólico)",
    "recommended_before" in router_mod.SYMBOLIC_DIRECT_INTENTS,
)
check(
    "recommended_before mapeia para o agente de disciplinas",
    router_mod.INTENT_TO_AGENT.get("recommended_before") == "disciplinas",
)
ns_mod = _import_module("neurosymbolic_validator", "src/neurosymbolic_validator.py")
check(
    "regra formal documentada em InferenceEngine.RULES",
    "sim_ementa" in ns_mod.InferenceEngine.RULES.get("recommended_before", "")
    and "ordem(a) < ordem(b)" in ns_mod.InferenceEngine.RULES["recommended_before"],
)
ie = ns_mod.InferenceEngine(kg)
check(
    "InferenceEngine.get_recommended_before delega ao KGC",
    {n for n, _ in ie.get_recommended_before(SO, n=5)} == nomes_so,
)

print(f"\n{BOLD}── query_graph + graph_payload com arestas inferidas ──{RESET}")
resp_rec = engine.query_graph("recommended_before", "sistemas operacionais") or ""
check(
    "resposta direta lista a recomendação com similaridade e a regra",
    f"Recomendadas antes de {SO}" in resp_rec
    and AOC in resp_rec
    and "recommended_before" in resp_rec
    and "não são pré-requisitos formais" in resp_rec,
    resp_rec[:120],
)
resp_chain_so = engine.query_graph("prerequisite_chain", "sistemas operacionais") or ""
check(
    "prerequisite_chain de SO ganha a seção 'Recomendadas antes (inferidas por conteúdo)'",
    "Recomendadas antes (inferidas por conteúdo)" in resp_chain_so
    and AOC in resp_chain_so,
    resp_chain_so[-200:],
)

gp_chain = engine.graph_payload("prerequisite_chain", "sistemas operacionais") or {}
inferidas = [e for e in gp_chain.get("edges", []) if e.get("inferida")]
check(
    "graph_payload da cadeia inclui aresta inferida → SO com confidence < 1",
    any(
        e["source"] == AOC and e["target"] == SO and 0 < e["confidence"] < 1
        for e in inferidas
    ),
    str(inferidas),
)
check(
    "nó extra inferido vem com flag inferida=True",
    any(n.get("inferida") for n in gp_chain.get("nodes", []) if n["nome"] == AOC),
)
check(
    "arestas formais da cadeia NÃO têm flag inferida",
    all(
        not e.get("inferida")
        for e in gp_chain.get("edges", [])
        if e not in inferidas
    ),
)

gp_rec = engine.graph_payload("recommended_before", "sistemas operacionais") or {}
check(
    "graph_payload do intent recommended_before: type + arestas inferidas",
    gp_rec.get("type") == "recommended_before"
    and gp_rec.get("edges")
    and all(e.get("inferida") and e["confidence"] < 1 for e in gp_rec["edges"]),
    str(gp_rec)[:160],
)

# Voltar ao estado sem embeddings: payload não deve quebrar
kg.kgc.set_embeddings(None)
kg.kgc._emb_model = None
kg.kgc.invalidate_cache()
check(
    "graph_payload recommended_before sem embeddings → None (sem grafo)",
    engine.graph_payload("recommended_before", "sistemas operacionais") is None,
)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
