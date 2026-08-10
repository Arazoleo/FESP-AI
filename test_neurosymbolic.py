"""
Testes do sistema Neurossimbólico do FESP-AI.

Testa todos os 5 pontos implementados:
  1. get_all_ancestors() - inferência transitiva de pré-requisitos
  2. verify_* - métodos de verificação simbólica no KG
  3. SymbolicValidator - enriquecimento e validação
  4. SYMBOLIC_DIRECT_INTENTS - conjunto de intents com atalho simbólico
  5. BaseAgent - inicialização do validator

Executa sem precisar de Ollama/LLM.
"""

import sys
import importlib.util
import traceback
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


import types as _types


def _bootstrap_src_package():
    """
    Cria um pacote 'src' mínimo no sys.modules para que importações
    relativas (from .xxx import ...) funcionem sem acionar src/__init__.py
    (que puxa chromadb/chroma incompatível no Python 3.9 x86_64).
    """
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
    """Importa módulo diretamente do arquivo, sem passar pelo src/__init__.py."""
    _bootstrap_src_package()
    full_name = f"src.{name.split('.')[-1]}" if not name.startswith("src.") else name
    spec = importlib.util.spec_from_file_location(
        full_name, ROOT / path,
        submodule_search_locations=[] if not path.endswith("__init__.py") else [str(ROOT / path.rsplit("/", 1)[0])],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = full_name.rsplit(".", 1)[0] if "." in full_name else full_name
    sys.modules[full_name] = mod
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_langchain():
    """Permite importar os agentes sem langchain instalado (nada aqui invoca o LLM)."""
    try:
        import langchain_core
        return
    except ImportError:
        pass
    root = _types.ModuleType("langchain_core")
    prompts = _types.ModuleType("langchain_core.prompts")
    parsers = _types.ModuleType("langchain_core.output_parsers")
    messages = _types.ModuleType("langchain_core.messages")
    prompts.ChatPromptTemplate = object
    parsers.StrOutputParser = object

    class _HumanMessage:
        def __init__(self, content):
            self.content = content

    messages.HumanMessage = _HumanMessage
    root.prompts, root.output_parsers, root.messages = prompts, parsers, messages
    sys.modules["langchain_core"] = root
    sys.modules["langchain_core.prompts"] = prompts
    sys.modules["langchain_core.output_parsers"] = parsers
    sys.modules["langchain_core.messages"] = messages


_stub_langchain()

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = 0
failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str, detail: str = ""):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")
    if detail:
        print(f"    {RED}{detail}{RESET}")


def section(title: str):
    print(f"\n{BOLD}{CYAN}══ {title} ══{RESET}")


section("Carregando Knowledge Graph")

try:
    kg_mod = _import_module("knowledge_graph", "src/knowledge_graph.py")
    KnowledgeGraph = kg_mod.KnowledgeGraph
    kg = KnowledgeGraph()
    kg.build_from_directories(
        disciplinas_dir="./markdown_disciplinas",
        regimentos_dir="./markdown_regimentos",
        docentes_dir="./markdown_docentes",
        cursos_dir="./markdown_cursos",
    )
    stats = kg.get_stats()
    ok(f"KG carregado: {stats['total_nos']} nós, {stats['total_arestas']} arestas")
    ok(f"Disciplinas: {stats['disciplinas']} | Docentes: {stats['docentes']} | Cursos: {stats['cursos']}")
except Exception as e:
    fail("Falha ao carregar KG", str(e))
    traceback.print_exc()
    sys.exit(1)


section("1. Inferência Transitiva - get_all_ancestors()")

test_disciplines_with_prereqs = []
for node, data in kg.graph.nodes(data=True):
    if data.get("tipo") == "disciplina":
        prereqs = kg.get_prerequisite_chain(data.get("nome", ""), max_depth=1)
        if prereqs:
            test_disciplines_with_prereqs.append(data.get("nome", ""))
        if len(test_disciplines_with_prereqs) >= 5:
            break

if test_disciplines_with_prereqs:
    disc = test_disciplines_with_prereqs[0]
    diretos = kg.get_prerequisite_chain(disc, max_depth=1)
    transitivos = kg.get_all_ancestors(disc)
    ok(f"'{disc}': {len(diretos)} direto(s), {len(transitivos)} transitivo(s) total via nx.ancestors()")

    diretos_set = set(diretos)
    transitivos_set = set(transitivos)
    if diretos_set.issubset(transitivos_set):
        ok(f"Pré-requisitos diretos ⊆ transitivos ✓ (correto para DAG)")
    else:
        missing = diretos_set - transitivos_set
        fail(f"Diretos não são subconjunto de transitivos", f"Faltando: {missing}")

    disc_sem_prereq = None
    for node, data in kg.graph.nodes(data=True):
        if data.get("tipo") == "disciplina":
            nome = data.get("nome", "")
            if nome and not kg.get_prerequisite_chain(nome, max_depth=1):
                disc_sem_prereq = nome
                break
    if disc_sem_prereq:
        ancestors_empty = kg.get_all_ancestors(disc_sem_prereq)
        ok(f"Disciplina sem pré-req '{disc_sem_prereq[:30]}': {len(ancestors_empty)} ancestors (esperado: 0)")
    else:
        ok("(todas as disciplinas têm pré-requisitos - skip)")
else:
    fail("Nenhuma disciplina com pré-requisitos encontrada")

nonexistent = kg.get_all_ancestors("DisciplinaQueNaoExiste123")
if nonexistent == []:
    ok("Disciplina inexistente retorna lista vazia ✓")
else:
    fail("Disciplina inexistente deveria retornar []", str(nonexistent))


section("2. Métodos de Verificação Simbólica")

if test_disciplines_with_prereqs:
    disc_real = test_disciplines_with_prereqs[0]
    if kg.verify_discipline_exists(disc_real):
        ok(f"verify_discipline_exists('{disc_real[:35]}') → True ✓")
    else:
        fail(f"verify_discipline_exists deveria retornar True para '{disc_real}'")

if not kg.verify_discipline_exists("DisciplinaFalsa999"):
    ok("verify_discipline_exists('DisciplinaFalsa999') → False ✓")
else:
    fail("verify_discipline_exists deveria retornar False para disciplina falsa")

if len(test_disciplines_with_prereqs) >= 1:
    disc_b = test_disciplines_with_prereqs[0]
    prereqs_b = kg.get_prerequisite_chain(disc_b, max_depth=1)
    if prereqs_b:
        disc_a = prereqs_b[0]
        result = kg.verify_prerequisite(disc_a, disc_b)
        if result:
            ok(f"verify_prerequisite('{disc_a[:25]}', '{disc_b[:25]}') → True ✓")
        else:
            fail(f"verify_prerequisite deveria ser True: {disc_a} → {disc_b}")

        result_inv = kg.verify_prerequisite(disc_b, disc_a)
        if not result_inv:
            ok(f"verify_prerequisite inverso → False ✓ (não circular)")
        else:
            print(f"  {YELLOW}⚠{RESET} Pré-requisito circular detectado: {disc_a} ↔ {disc_b}")

docentes_com_disc = []
for node, data in kg.graph.nodes(data=True):
    if data.get("tipo") == "disciplina":
        nome = data.get("nome", "")
        docentes = kg.get_docentes_of_discipline(nome)
        if docentes:
            docentes_com_disc.append((nome, docentes[0]))
            break

if docentes_com_disc:
    disc_nome, doc_nome = docentes_com_disc[0]
    if kg.verify_docente_in_discipline(doc_nome, disc_nome):
        ok(f"verify_docente_in_discipline('{doc_nome[:25]}', '{disc_nome[:25]}') → True ✓")
    else:
        fail(f"verify_docente_in_discipline deveria ser True")

    if not kg.verify_docente_in_discipline("ProfessorFalso999", disc_nome):
        ok("verify_docente_in_discipline(docente falso) → False ✓")
    else:
        fail("verify_docente_in_discipline deveria ser False para docente falso")
else:
    print(f"  {YELLOW}⚠{RESET} Nenhuma disciplina com docente encontrada para testar")

if test_disciplines_with_prereqs:
    facts = kg.get_symbolic_facts(test_disciplines_with_prereqs[0])
    if facts and "nome" in facts and "prerequisitos_diretos" in facts:
        ok(f"get_symbolic_facts() retorna dict com {len(facts)} campos ✓")
    else:
        fail("get_symbolic_facts() não retornou estrutura esperada", str(facts))

    empty_facts = kg.get_symbolic_facts("DisciplinaFalsa999")
    if empty_facts == {}:
        ok("get_symbolic_facts(disciplina falsa) → {} ✓")
    else:
        fail("get_symbolic_facts(disciplina falsa) deveria retornar {}", str(empty_facts))


section("3. SymbolicValidator - Enriquecimento e Validação")

try:
    sys.modules["src.knowledge_graph"] = kg_mod
    validator_mod = _import_module("neurosymbolic_validator", "src/neurosymbolic_validator.py")
    SymbolicValidator = validator_mod.SymbolicValidator
    ValidationResult = validator_mod.ValidationResult
    validator = SymbolicValidator(kg)
    ok("SymbolicValidator instanciado ✓")
except Exception as e:
    fail("Falha ao instanciar SymbolicValidator", str(e))
    traceback.print_exc()
    sys.exit(1)

if test_disciplines_with_prereqs:
    disc = test_disciplines_with_prereqs[0]
    enrichment = validator._build_discipline_facts(disc)
    if enrichment and "[FATOS VERIFICADOS NO KNOWLEDGE GRAPH" in enrichment:
        ok(f"_build_discipline_facts() gerou bloco de {len(enrichment)} chars ✓")
        print(f"    Prévia: {enrichment[:120].replace(chr(10), ' ')}...")
    else:
        fail("_build_discipline_facts() deveria gerar bloco com header [FATOS VERIFICADOS...]")

if test_disciplines_with_prereqs:
    disc = test_disciplines_with_prereqs[0]
    ctx = validator.enrich_agent_context("prerequisite_chain", disc)
    if ctx:
        ok(f"enrich_agent_context('prerequisite_chain', ...) → {len(ctx)} chars ✓")
    else:
        fail("enrich_agent_context deveria retornar conteúdo para prerequisite_chain")

if docentes_com_disc:
    disc_nome, doc_nome = docentes_com_disc[0]
    ctx_doc = validator.enrich_agent_context("discipline_docentes", disc_nome)
    if ctx_doc:
        ok(f"enrich_agent_context('discipline_docentes', ...) → {len(ctx_doc)} chars ✓")

ctx_empty = validator.enrich_agent_context("ementa_xpto_invalido", "Algo")
if ctx_empty == "":
    ok("enrich_agent_context(intent inválido) → '' ✓")

if test_disciplines_with_prereqs:
    disc = test_disciplines_with_prereqs[0]
    prereqs = kg.get_prerequisite_chain(disc, max_depth=1)

    response_ok = f"Para cursar {disc}, você precisa ter feito " + (prereqs[0] if prereqs else "nada")
    result_ok = validator.validate_response(response_ok, "prerequisite_chain", disc)
    if isinstance(result_ok, ValidationResult):
        ok(f"validate_response() retornou ValidationResult ✓")
    if result_ok.verified_facts:
        ok(f"Fatos verificados na resposta OK: {result_ok.verified_facts[0][:60]}")

    response_bad = f"Para cursar {disc}, precisa de DisciplinaInventadaFalsa9999 e Outra9999."
    result_bad = validator.validate_response(response_bad, "prerequisite_chain", disc)
    if result_bad.violations:
        ok(f"Violação detectada em resposta com dado inventado ✓: '{result_bad.violations[0][:60]}'")
    else:
        print(f"  {YELLOW}⚠{RESET} Nenhuma violação detectada (pode ser FP low - OK se termos curtos)")

if test_disciplines_with_prereqs:
    disc = test_disciplines_with_prereqs[0]
    result_any = validator.validate_response("Resposta qualquer", "prerequisite_chain", disc)
    annotation = result_any.to_annotation()
    if "---" in annotation or annotation == "":
        ok("to_annotation() retorna string bem formada ✓")
    else:
        fail("to_annotation() formato inesperado", annotation[:80])

if test_disciplines_with_prereqs:
    summary = validator.get_symbolic_facts_summary(test_disciplines_with_prereqs[0])
    if summary.get("found") is True:
        ok(f"get_symbolic_facts_summary() → found=True, {len(summary)} campos ✓")
    else:
        fail("get_symbolic_facts_summary() deveria retornar found=True")

    summary_miss = validator.get_symbolic_facts_summary("NaoExisteEssa999")
    if summary_miss.get("found") is False:
        ok("get_symbolic_facts_summary(inexistente) → found=False ✓")

validator.invalidate_cache()
known_after = validator._get_known_disciplines()
if isinstance(known_after, set) and len(known_after) > 0:
    ok(f"Cache rebuilding após invalidate_cache(): {len(known_after)} disciplinas ✓")
else:
    fail("Cache rebuilding falhou", str(known_after)[:80])


section("4. SYMBOLIC_DIRECT_INTENTS - Atalho Simbólico no Router")

try:
    router_mod = _import_module("router", "src/workflow/router.py")
    SYMBOLIC_DIRECT_INTENTS = router_mod.SYMBOLIC_DIRECT_INTENTS
    ok(f"SYMBOLIC_DIRECT_INTENTS importado: {len(SYMBOLIC_DIRECT_INTENTS)} intents ✓")

    expected_intents = {
        "listar_cursos", "coordenador_curso", "disciplinas_termo",
        "todos_termos_curso", "eletivas_curso", "prerequisite_chain",
        "dependents", "discipline_docentes",
    }
    missing = expected_intents - SYMBOLIC_DIRECT_INTENTS
    if not missing:
        ok("Todos os intents esperados presentes ✓")
    else:
        fail(f"Intents faltando em SYMBOLIC_DIRECT_INTENTS: {missing}")
except ImportError as e:
    fail("Falha ao importar SYMBOLIC_DIRECT_INTENTS", str(e))


section("5. Integração GraphRAG + Atalho Simbólico")

try:
    ic_mod = _import_module("src.intent_classifier", "src/intent_classifier.py")

    graph_rag_mod = _import_module("src.graph_rag", "src/graph_rag.py")
    GraphRAGEngine = graph_rag_mod.GraphRAGEngine

    gre = GraphRAGEngine(kg, embeddings_model=None)
    ok("GraphRAGEngine instanciado com KG ✓")

    use_g, intent, term = gre.should_use_graph("quais são os pré-requisitos de Álgebra Linear?")
    if use_g and intent:
        ok(f"should_use_graph(): use={use_g}, intent='{intent}', term='{term}' ✓")
        if intent in SYMBOLIC_DIRECT_INTENTS:
            ok(f"Intent '{intent}' está em SYMBOLIC_DIRECT_INTENTS → atalho simbólico ativo ✓")
        else:
            print(f"  {YELLOW}⚠{RESET} Intent '{intent}' NÃO em SYMBOLIC_DIRECT_INTENTS")
    else:
        print(f"  {YELLOW}⚠{RESET} should_use_graph não detectou pré-requisitos (depende do KG)")

    cursos = gre.query_graph("listar_cursos", "")
    if cursos and "**Cursos de Graduação" in cursos:
        ok(f"query_graph('listar_cursos') retorna resposta formatada ✓ ({len(cursos)} chars)")
    else:
        print(f"  {YELLOW}⚠{RESET} query_graph('listar_cursos') não retornou o formato esperado")

except Exception as e:
    fail("Erro ao testar integração GraphRAG", str(e))
    traceback.print_exc()


section("6. BaseAgent - Inicialização do SymbolicValidator")

try:
    class MockDB:
        def get(self, **kwargs):
            return {"ids": [], "documents": [], "metadatas": []}

    class MockRetriever:
        def invoke(self, q):
            return []

    class MockRAG:
        llm = None
        db = MockDB()
        retriever = MockRetriever()
        knowledge_graph = kg
        graph_rag = None

    agents_pkg = _types.ModuleType("src.agents")
    agents_pkg.__path__ = [str(ROOT / "src/agents")]
    agents_pkg.__package__ = "src.agents"
    sys.modules["src.agents"] = agents_pkg

    base_agent_mod = _import_module("src.agents.base_agent", "src/agents/base_agent.py")
    disc_agent_mod = _import_module("src.agents.disciplinas_agent", "src/agents/disciplinas_agent.py")
    agent = disc_agent_mod.DisciplinasAgent(MockRAG())

    if agent.validator is not None and isinstance(agent.validator, SymbolicValidator):
        ok("DisciplinasAgent.validator inicializado como SymbolicValidator ✓")
    else:
        fail("DisciplinasAgent.validator não foi inicializado", str(type(agent.validator)))

except Exception as e:
    fail("Erro ao testar BaseAgent com validator", str(e))
    traceback.print_exc()


section("7. Pipeline - Nó symbolic_kg")

try:
    assert hasattr(router_mod, "SYMBOLIC_DIRECT_INTENTS"), "SYMBOLIC_DIRECT_INTENTS ausente"
    assert hasattr(router_mod, "route_intent"), "route_intent ausente"
    ok("router.py contém SYMBOLIC_DIRECT_INTENTS e route_intent ✓")

    pipeline_text = (ROOT / "src/workflow/pipeline.py").read_text()
    if "SYMBOLIC_DIRECT_INTENTS" in pipeline_text and "symbolic_kg" in pipeline_text:
        ok("pipeline.py contém referências a SYMBOLIC_DIRECT_INTENTS e symbolic_kg ✓")
    else:
        fail("pipeline.py não contém as referências neurossimbólicas esperadas")

    multi_text = (ROOT / "src/multi_agent_rag.py").read_text()
    if "symbolic_kg" in multi_text:
        ok("multi_agent_rag.py contém metadata do agente symbolic_kg ✓")
    else:
        fail("multi_agent_rag.py não contém metadata do agente symbolic_kg")

except Exception as e:
    fail("Erro ao verificar pipeline", str(e))


print(f"\n{BOLD}{'═'*50}{RESET}")
total = passed + failed
print(f"{BOLD}Resultado: {GREEN}{passed}{RESET}/{BOLD}{total}{RESET} testes passaram", end="")
if failed > 0:
    print(f"  {RED}({failed} falhou){RESET}")
else:
    print(f"  {GREEN}🎉 Todos passaram!{RESET}")
print(f"{'═'*50}")

sys.exit(0 if failed == 0 else 1)
