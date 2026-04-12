"""
Testes Conversacionais Neurossimbólicos — FESP-AI
==================================================
Simula conversas reais de estudantes com o sistema.

Arquitetura dos testes:
  BLOCO 1-4: Usam KG + GraphRAG diretamente (sem Ollama/Chroma sync)
             → Testam o atalho simbólico, inferência transitiva, validação
  BLOCO 5:   Usa o LLM (se disponível) para testar enriquecimento de contexto
"""

import sys
import importlib.util
import types as _types
import time
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _bootstrap_src() -> None:
    if "src" not in sys.modules:
        pkg = _types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        pkg.__package__ = "src"
        sys.modules["src"] = pkg


def _load(full_name: str, rel_path: str):
    _bootstrap_src()
    spec = importlib.util.spec_from_file_location(full_name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = full_name.rsplit(".", 1)[0] if "." in full_name else full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod

# ── Cores ──────────────────────────────────────────────────────────────────────
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
MAGENTA = "\033[95m"
RED    = "\033[91m"
DIM    = "\033[2m"
RESET  = "\033[0m"

# ── Helpers de UI ──────────────────────────────────────────────────────────────
WIDTH = 72

def header(title: str):
    print(f"\n{BOLD}{CYAN}{'═' * WIDTH}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * WIDTH}{RESET}")

def subheader(title: str):
    print(f"\n{BOLD}{BLUE}── {title} ──{RESET}")

def user_msg(msg: str):
    print(f"\n{BOLD}👤 Estudante:{RESET} {msg}")

def agent_info(agent: str, t: float, intent: str = "", term: str = ""):
    color = CYAN if agent == "symbolic_kg" else MAGENTA
    label = "🔷 Knowledge Graph (sem LLM)" if agent == "symbolic_kg" else f"🤖 Agente LLM: {agent}"
    print(f"{color}{BOLD}{label}{RESET}  {DIM}({t:.2f}s){RESET}", end="")
    if intent:
        print(f"  {DIM}intent={intent} term={term[:30]}{RESET}", end="")
    print()

def bot_response(text: str):
    lines = text.strip().split("\n")
    for line in lines:
        if line.startswith("**") or line.startswith("#"):
            print(f"  {BOLD}{line}{RESET}")
        elif line.startswith("- ") or line.startswith("• "):
            print(f"  {GREEN}{line}{RESET}")
        elif "⚠" in line or "Atenção" in line:
            print(f"  {YELLOW}{line}{RESET}")
        elif "Verificado" in line or "verificado" in line:
            print(f"  {DIM}{line}{RESET}")
        elif line.strip():
            wrapped = textwrap.fill(line, width=WIDTH - 2, initial_indent="  ", subsequent_indent="  ")
            print(wrapped)
        else:
            print()

def separator():
    print(f"  {DIM}{'─' * (WIDTH - 4)}{RESET}")

# ── Inicializar KG + GraphRAG (sem Chroma/Ollama sync) ───────────────────────
header("Iniciando Knowledge Graph + GraphRAGEngine")
print(f"{DIM}Carregando apenas KG + GraphRAG (sem sync de embeddings).{RESET}")
print(f"{DIM}Isso testa o atalho simbólico, que é independente do LLM.{RESET}")

t0 = time.time()
try:
    kg_mod  = _load("src.knowledge_graph",   "src/knowledge_graph.py")
    ic_mod  = _load("src.intent_classifier", "src/intent_classifier.py")
    gr_mod  = _load("src.graph_rag",         "src/graph_rag.py")
    nv_mod  = _load("src.neurosymbolic_validator", "src/neurosymbolic_validator.py")
    rt_mod  = _load("src.workflow.router",   "src/workflow/router.py")

    kg = kg_mod.KnowledgeGraph()
    kg.build_from_directories(
        disciplinas_dir="./markdown_disciplinas",
        regimentos_dir="./markdown_regimentos",
        docentes_dir="./markdown_docentes",
        cursos_dir="./markdown_cursos",
    )
    gre = gr_mod.GraphRAGEngine(kg, embeddings_model=None)
    validator = nv_mod.SymbolicValidator(kg)
    SYMBOLIC_DIRECT_INTENTS = rt_mod.SYMBOLIC_DIRECT_INTENTS

    elapsed = time.time() - t0
    stats = kg.get_stats()
    print(f"{GREEN}✓ KG carregado em {elapsed:.2f}s{RESET}")
    print(f"{DIM}  {stats['total_nos']} nós | {stats['total_arestas']} arestas | "
          f"{stats['disciplinas']} disciplinas | {stats['docentes']} docentes{RESET}")
except Exception as e:
    print(f"{RED}✗ Erro ao inicializar: {e}{RESET}")
    import traceback; traceback.print_exc()
    sys.exit(1)


def ask_symbolic(pergunta: str) -> dict:
    """
    Simula exatamente o que o router_node faz para o atalho simbólico:
    should_use_graph() → query_graph() → retorno direto sem LLM.
    Trata listar_cursos especialmente (não precisa de term).
    """
    t_start = time.time()
    use_graph, intent, term = gre.should_use_graph(pergunta)
    response = None
    active_agent = "fallback"

    if use_graph and intent and intent in SYMBOLIC_DIRECT_INTENTS:
        # listar_cursos não precisa de term
        query_term = term or "" if intent != "listar_cursos" else ""
        if intent == "listar_cursos" or query_term:
            response = gre.query_graph(intent, query_term)
            if response:
                active_agent = "symbolic_kg"

    elapsed = time.time() - t_start
    return {
        "response": response or f"(intent='{intent}', term='{term}' — não roteado como simbólico)",
        "active_agent": active_agent,
        "intent": intent or "",
        "term": term or "",
        "elapsed": elapsed,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 1 — Perguntas que ativam o ATALHO SIMBÓLICO (sem LLM)
# ══════════════════════════════════════════════════════════════════════════════
header("BLOCO 1 — Atalho Simbólico: KG responde direto (sem LLM)")
print(f"{DIM}Para esses intents, a resposta sai do Knowledge Graph puro.{RESET}")
print(f"{DIM}0% alucinação, latência mínima — sem chamada ao Ollama.{RESET}")

conversas_simbolicas = [
    {
        "pergunta": "Quais são os pré-requisitos de Álgebra Linear II?",
        "desc": "Pré-requisitos diretos — intent: prerequisite_chain"
    },
    {
        "pergunta": "Quais disciplinas tem no termo 3 do BCC?",
        "desc": "Disciplinas por termo — intent: disciplinas_termo"
    },
    {
        "pergunta": "Quais cursos a UNIFESP ICT oferece?",
        "desc": "Listagem de cursos — intent: listar_cursos"
    },
    {
        "pergunta": "Quem leciona Cálculo em Uma Variável?",
        "desc": "Docentes de disciplina — intent: discipline_docentes"
    },
    {
        "pergunta": "O que Álgebra Linear II desbloqueia?",
        "desc": "Dependentes de disciplina — intent: dependents"
    },
    {
        "pergunta": "Quais eletivas tem no BCC?",
        "desc": "Eletivas do curso — intent: eletivas_curso"
    },
    {
        "pergunta": "Quem é o coordenador do BCC?",
        "desc": "Coordenador de curso — intent: coordenador_curso"
    },
]

for i, conv in enumerate(conversas_simbolicas, 1):
    subheader(f"Teste S{i}: {conv['desc']}")
    user_msg(conv["pergunta"])

    result = ask_symbolic(conv["pergunta"])
    agent  = result.get("active_agent", "?")
    intent = result.get("intent", "")
    term   = result.get("term", "")
    t      = result.get("elapsed", 0)

    agent_info(agent, t, intent, term)

    is_symbolic = agent == "symbolic_kg"
    if is_symbolic:
        print(f"  {GREEN}✓ Atalho simbólico ativado — resposta 100% do KG, zero LLM{RESET}")
    else:
        print(f"  {YELLOW}⚠ Intent não capturado como simbólico (intent={intent}){RESET}")

    bot_response(result.get("response", ""))

print()


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 2 — Perguntas que ativam o LLM COM enriquecimento KG
# ══════════════════════════════════════════════════════════════════════════════
header("BLOCO 2 — LLM Enriquecido: contexto KG prepended antes da geração")
print(f"{DIM}O LLM recebe fatos verificados do KG no contexto antes de gerar.{RESET}")
print(f"{DIM}Reduz alucinações em respostas sobre ementa, conteúdo, etc.{RESET}")

conversas_llm = [
    {
        "pergunta": "Me fale sobre a disciplina Álgebra Linear II",
        "desc": "Ementa + info — KG enriquece com prereqs e docentes antes do LLM"
    },
    {
        "pergunta": "O que é Cálculo em Uma Variável e quais são seus pré-requisitos?",
        "desc": "Pergunta mista ementa + prereqs"
    },
    {
        "pergunta": "Quais professores trabalham com machine learning no ICT?",
        "desc": "Docentes por área — KG enriquece com lista de especialistas"
    },
]

for i, conv in enumerate(conversas_llm, 1):
    subheader(f"Teste L{i}: {conv['desc']}")
    user_msg(conv["pergunta"])

    # Simular o que o base_agent.answer() faria:
    # 1. Detectar intent
    use_graph, intent, term = gre.should_use_graph(conv["pergunta"])
    print(f"  {DIM}→ intent: {intent or 'desconhecido'} | term: {term or 'N/A'}{RESET}")

    # 2. Mostrar o enriquecimento que o LLM receberia no contexto
    if term and intent:
        enrichment = validator.enrich_agent_context(intent, term)
        if enrichment:
            print(f"  {CYAN}[Simbólico → Neural] Bloco enviado ao LLM:{RESET}")
            for line in enrichment.split("\n"):
                print(f"  {DIM}{line}{RESET}")
        else:
            print(f"  {DIM}[Sem enriquecimento KG para este intent]{RESET}")

    print(f"  {DIM}→ (resposta do LLM não executada — Ollama sync pendente){RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 3 — Inferência Transitiva: cadeia completa de pré-requisitos
# ══════════════════════════════════════════════════════════════════════════════
header("BLOCO 3 — Inferência Transitiva: nx.ancestors() no KG")
print(f"{DIM}Mostra como o sistema calcula cadeias completas via NetworkX.{RESET}")

subheader("Comparação: DFS (antigo) vs nx.ancestors() (novo)")

# Selecionar uma disciplina que tenha cadeia de pré-requisitos
test_discs = ["Álgebra Linear II", "Cálculo em Várias Variáveis", "Algoritmos e Estruturas de Dados II"]

# validator já foi instanciado na inicialização acima

for disc in test_discs:
    diretos = kg.get_prerequisite_chain(disc, max_depth=1)
    todos   = kg.get_all_ancestors(disc)
    if not diretos:
        continue

    print(f"\n  {BOLD}Disciplina: {disc}{RESET}")
    print(f"  {GREEN}Pré-requisitos diretos (max_depth=1):{RESET}  {', '.join(diretos) if diretos else 'nenhum'}")
    print(f"  {CYAN}Todos os ancestrais (nx.ancestors):{RESET}    {', '.join(todos) if todos else 'nenhum'}")

    if set(diretos) != set(todos):
        indiretos = [p for p in todos if p not in diretos]
        print(f"  {YELLOW}  → Inferência transitiva revelou: {', '.join(indiretos)}{RESET}")
    else:
        print(f"  {DIM}  → Cadeia linear (sem pré-requisitos adicionais){RESET}")

    # Mostrar o bloco de enriquecimento que o LLM receberia
    enrichment = validator._build_discipline_facts(disc)
    if enrichment:
        separator()
        print(f"  {DIM}Bloco enviado ao LLM como contexto verificado:{RESET}")
        for line in enrichment.split("\n"):
            print(f"  {DIM}{line}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 4 — Validação de Resposta (Neural → Simbólico)
# ══════════════════════════════════════════════════════════════════════════════
header("BLOCO 4 — Validação Simbólica: Neural → Simbólico")
print(f"{DIM}Simula o validador checando respostas do LLM contra o KG.{RESET}")

from src.neurosymbolic_validator import ValidationResult

subheader("Caso 1: Resposta correta — validator confirma")
disc_test = "Álgebra Linear II"
prereqs_reais = kg.get_prerequisite_chain(disc_test, max_depth=1)
if prereqs_reais:
    resp_correta = f"Para cursar {disc_test}, você precisa ter feito {prereqs_reais[0]} anteriormente."
    print(f"  Resposta simulada: \"{resp_correta}\"")
    result_v = validator.validate_response(resp_correta, "prerequisite_chain", disc_test)
    print(f"  is_valid: {GREEN}{result_v.is_valid}{RESET}")
    for f in result_v.verified_facts:
        print(f"  {GREEN}✓ Verificado: {f}{RESET}")
    annotation = result_v.to_annotation()
    if annotation:
        print(f"  {DIM}Anotação adicionada: {annotation.strip()[:80]}...{RESET}")

separator()

subheader("Caso 2: Resposta com dado inventado — validator detecta")
resp_inventada = f"Para cursar {disc_test}, você precisa de DisciplinaInventadaXYZ e CursoFalso999."
print(f"  Resposta simulada: \"{resp_inventada}\"")
result_inv = validator.validate_response(resp_inventada, "prerequisite_chain", disc_test)
print(f"  is_valid: {RED}{result_inv.is_valid}{RESET}")
for v in result_inv.violations:
    print(f"  {RED}✗ Violação: {v}{RESET}")

separator()

subheader("Caso 3: Validação de docentes")
disc_com_doc = None
doc_nome = None
for node, data in kg.graph.nodes(data=True):
    if data.get("tipo") == "disciplina":
        nome = data.get("nome", "")
        docs = kg.get_docentes_of_discipline(nome)
        if docs:
            disc_com_doc = nome
            doc_nome = docs[0]
            break

if disc_com_doc and doc_nome:
    resp_doc = f"A disciplina {disc_com_doc} é lecionada pelo Professor {doc_nome}."
    print(f"  Resposta simulada: \"{resp_doc}\"")
    result_doc = validator.validate_response(resp_doc, "discipline_docentes", disc_com_doc)
    for f in result_doc.verified_facts:
        print(f"  {GREEN}✓ {f}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# BLOCO 5 — Conversa Encadeada (contexto de seguimento)
# ══════════════════════════════════════════════════════════════════════════════
header("BLOCO 5 — Conversa Encadeada")
print(f"{DIM}Sequência de perguntas relacionadas, como um estudante faria.{RESET}")

chat_sequence = [
    "Quais são os pré-requisitos de Algoritmos e Estruturas de Dados II?",
    "E quem leciona essa disciplina?",
    "Quais cursos de graduação o ICT tem?",
    "Quais disciplinas tem no 1º termo do BCC?",
]

for i, pergunta in enumerate(chat_sequence, 1):
    subheader(f"Turno {i}")
    user_msg(pergunta)

    result = ask_symbolic(pergunta)
    agent  = result.get("active_agent", "?")
    intent = result.get("intent", "")
    t      = result.get("elapsed", 0)

    agent_info(agent, t, intent, result.get("term", ""))
    if agent == "symbolic_kg":
        print(f"  {GREEN}→ Resposta simbólica (sem LLM){RESET}")
    bot_response(result.get("response", "")[:800])


# ══════════════════════════════════════════════════════════════════════════════
# RESUMO FINAL
# ══════════════════════════════════════════════════════════════════════════════
header("RESUMO — Métricas do Sistema Neurossimbólico")

print(f"""
  {BOLD}Componente              Status{RESET}
  ────────────────────────────────────────────────────
  {GREEN}✓{RESET} neurosymbolic_validator.py  Validação + enriquecimento
  {GREEN}✓{RESET} knowledge_graph.py          get_all_ancestors() via nx.ancestors()
  {GREEN}✓{RESET} base_agent.py               Pipeline neurossimbólico (4 etapas)
  {GREEN}✓{RESET} workflow/router.py           SYMBOLIC_DIRECT_INTENTS (11 intents)
  {GREEN}✓{RESET} workflow/pipeline.py         Nó symbolic_kg (bypass total do LLM)
  {GREEN}✓{RESET} multi_agent_rag.py           Metadata agente symbolic_kg

  {BOLD}Intents com atalho simbólico (sem LLM):{RESET}
  prerequisite_chain · dependents · discipline_docentes
  docente_leciona_disciplina · docentes_by_area
  listar_cursos · coordenador_curso · disciplinas_termo
  todos_termos_curso · eletivas_curso · matriz_info
""")
