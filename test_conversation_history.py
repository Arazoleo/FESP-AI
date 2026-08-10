"""
Testes de regressão da continuidade de conversa.

Motivação: cada mensagem começava com "Olá!" porque o histórico nunca chegava
aos prompts dos agentes - todo turno parecia o primeiro para o LLM.

Verifica a montagem do prompt (sem invocar LLM):
  - com histórico: bloco HISTORICO + regra de não re-saudação antes da pergunta
  - sem histórico (primeiro turno): template intacto (saudação permitida)
"""

import sys
import importlib.util
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _stub_langchain():
    try:
        import langchain_core
        return
    except ImportError:
        pass
    root = _types.ModuleType("langchain_core")
    prompts = _types.ModuleType("langchain_core.prompts")
    parsers = _types.ModuleType("langchain_core.output_parsers")
    prompts.ChatPromptTemplate = object
    parsers.StrOutputParser = object
    root.prompts, root.output_parsers = prompts, parsers
    sys.modules["langchain_core"] = root
    sys.modules["langchain_core.prompts"] = prompts
    sys.modules["langchain_core.output_parsers"] = parsers


def _stub_langgraph():
    try:
        import langgraph.graph
        return
    except ImportError:
        pass

    class _StateGraph:
        def __init__(self, *a, **k): pass
        def add_node(self, *a, **k): pass
        def set_entry_point(self, *a, **k): pass
        def add_conditional_edges(self, *a, **k): pass
        def add_edge(self, *a, **k): pass
        def compile(self): return None

    root = _types.ModuleType("langgraph")
    graph = _types.ModuleType("langgraph.graph")
    graph.StateGraph = _StateGraph
    graph.END = "END"
    root.graph = graph
    sys.modules["langgraph"] = root
    sys.modules["langgraph.graph"] = graph


def _import_module(full_name: str, path: str):
    for pkg_name, pkg_path in (
        ("src", ROOT / "src"),
        ("src.agents", ROOT / "src/agents"),
        ("src.workflow", ROOT / "src/workflow"),
    ):
        if pkg_name not in sys.modules:
            pkg = _types.ModuleType(pkg_name)
            pkg.__path__ = [str(pkg_path)]
            pkg.__package__ = pkg_name
            sys.modules[pkg_name] = pkg
    spec = importlib.util.spec_from_file_location(full_name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = full_name.rsplit(".", 1)[0]
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


_stub_langchain()
base_mod = _import_module("src.agents.base_agent", "src/agents/base_agent.py")
disc_mod = _import_module("src.agents.disciplinas_agent", "src/agents/disciplinas_agent.py")
conv_mod = _import_module("src.agents.conversa_agent", "src/agents/conversa_agent.py")


class _FakeRag:
    llm = None
    db = None
    retriever = None
    graph_rag = None
    knowledge_graph = None


disc = disc_mod.DisciplinasAgent(_FakeRag())
conv = conv_mod.ConversaAgent(_FakeRag())

HIST = "Aluno: Quais os pré-requisitos de Compiladores?\nAssistente: A cadeia é..."

print(f"{BOLD}── BaseAgent._apply_history ──{RESET}")
template = disc.get_prompt_template()
com_hist = disc._apply_history(template, HIST)
check("com histórico, bloco HISTORICO é inserido", "HISTORICO RECENTE DA CONVERSA" in com_hist)
check("com histórico, regra de não re-saudação presente", "NAO cumprimente" in com_hist)
check("placeholder {history} presente para o invoke", "{history}" in com_hist)
check(
    "bloco vem ANTES da pergunta",
    com_hist.find("HISTORICO RECENTE") < com_hist.find("Pergunta: {question}"),
)
check("pergunta original preservada", "Pergunta: {question}" in com_hist)
check("sem histórico, template fica intacto", disc._apply_history(template, "") == template)
check(
    "todos os templates de domínio têm o ponto de inserção",
    "Pergunta: {question}" in template,
)

print(f"\n{BOLD}── answer() aceita history em todos os agentes ──{RESET}")
import inspect
doc_mod = _import_module("src.agents.docentes_agent", "src/agents/docentes_agent.py")
cur_mod = _import_module("src.agents.cursos_agent", "src/agents/cursos_agent.py")
reg_mod = _import_module("src.agents.regimentos_agent", "src/agents/regimentos_agent.py")
for cls in (
    disc_mod.DisciplinasAgent, doc_mod.DocentesAgent, cur_mod.CursosAgent,
    reg_mod.RegimentosAgent, conv_mod.ConversaAgent,
):
    sig = inspect.signature(cls.answer)
    check(f"{cls.__name__}.answer tem parâmetro history", "history" in sig.parameters)

print(f"\n{BOLD}── ConversaAgent (o maior emissor de 'Olá!') ──{RESET}")
tpl = conv.get_prompt_template()
substituido = tpl.replace(
    "O usuario disse: {question}",
    "HISTORICO RECENTE DA CONVERSA:\n{history}\n\n"
    "A conversa JA ESTA EM ANDAMENTO: nao se reapresente nem cumprimente "
    "de novo (a menos que o usuario esteja claramente cumprimentando agora).\n\n"
    "O usuario disse: {question}",
    1,
)
check("template do conversa tem o ponto de inserção", substituido != tpl)

print(f"\n{BOLD}── Anáfora de curso no ContextResolver ──{RESET}")
cr_mod = _import_module("src.context_resolver", "src/context_resolver.py")
resolver = cr_mod.ContextResolver()
resolver.update_context("t1", "Como funciona a Matriz Curricular do BCC?", "user")
hist_msgs = [
    {"role": "user", "content": "Como funciona a Matriz Curricular do BCC?"},
    {"role": "assistant", "content": "O curso tem 8 termos..."},
]
resolved, modified = resolver.resolve_question(
    "E tem como saber algumas dessas eletivas?", "t1", hist_msgs
)
check(
    "'dessas eletivas' herda o curso do contexto",
    modified and resolved == "Quais as eletivas de BCC?",
    f"obteve {resolved!r}",
)
resolved2, _ = resolver.resolve_question("e a matriz dele?", "t1", hist_msgs)
check(
    "'a matriz dele' herda o curso",
    "BCC" in resolved2,
    f"obteve {resolved2!r}",
)
resolved3, mod3 = resolver.resolve_question(
    "Quais as eletivas de EC?", "t1", hist_msgs
)
check(
    "pergunta com curso explícito NÃO é reescrita",
    not mod3,
    f"obteve {resolved3!r}",
)
resolved4, mod4 = resolver.resolve_question(
    "E quais as disciplinas que tenho que fazer?", "t1", hist_msgs
)
check(
    "'disciplinas que tenho que fazer' herda o curso (grade, não críticas globais)",
    mod4 and resolved4 == "Quais as disciplinas de BCC?",
    f"obteve {resolved4!r}",
)

print(f"\n{BOLD}── Troca de entidade mid-conversation (T8) ──{RESET}")
t8 = cr_mod.ContextResolver()
T8_MSG1 = "Quais os pré-requisitos de Redes de Computadores?"
T8_R1 = "Para você cursar Redes de Computadores, é necessário: Sistemas Operacionais e Algoritmos."
T8_MSG2 = "e sobre Banco de Dados?"
T8_R2 = (
    "A disciplina de Banco de Dados (Código: 2831) tem 72h. "
    "Ela é pré-requisito para cursar Projetos em Engenharia de Computação."
)
t8.update_context("t8", T8_MSG1, "user")
t8.update_context("t8", T8_R1, "assistant")
t8_hist2 = [
    {"role": "user", "content": T8_MSG1},
    {"role": "assistant", "content": T8_R1},
]
for m in t8_hist2:
    t8.update_context("t8", m["content"], m["role"])
t8_res2, t8_mod2 = t8.resolve_question(T8_MSG2, "t8", t8_hist2)
check(
    "T2: 'e sobre Banco de Dados?' troca a entidade",
    t8_mod2 and "Banco de Dados" in t8_res2,
    f"obteve {t8_res2!r}",
)
t8.update_context("t8", T8_MSG2, "user")
t8.update_context("t8", T8_R2, "assistant")
check(
    "T2: resposta do assistente NÃO reverte a disciplina do usuário",
    t8.get_context("t8").disciplina == "Banco de Dados",
    f"obteve {t8.get_context('t8').disciplina!r}",
)
t8_hist3 = t8_hist2 + [
    {"role": "user", "content": T8_MSG2},
    {"role": "assistant", "content": T8_R2},
]
for m in t8_hist3:
    t8.update_context("t8", m["content"], m["role"])
t8_res3, t8_mod3 = t8.resolve_question("qual a ementa?", "t8", t8_hist3)
check(
    "T3: 'qual a ementa?' herda a entidade TROCADA (Banco de Dados)",
    t8_mod3 and t8_res3 == "Qual a ementa de Banco de Dados?",
    f"obteve {t8_res3!r}",
)
t8b = cr_mod.ContextResolver()
t8b.update_context("t8b", "estou meio perdido com o curso", "user")
t8b.update_context(
    "t8b", "A disciplina de Lógica de Programação (código 1234) cobre o básico.", "assistant"
)
check(
    "sem entidade explícita do usuário, assistente ainda define a disciplina",
    t8b.get_context("t8b").disciplina == "Lógica de Programação",
    f"obteve {t8b.get_context('t8b').disciplina!r}",
)

print(f"\n{BOLD}── LLM-first: reescrita de follow-up (bug do AIMessage) ──{RESET}")


class _AIMessage:
    def __init__(self, content):
        self.content = content


class _FakeRewriteLLM:
    """Simula chat model: invoke() retorna AIMessage, não str."""
    def invoke(self, prompt):
        return _AIMessage("Quais as eletivas de BCC?")


rewritten = resolver.rewrite_with_llm(
    "E tem como saber algumas dessas eletivas?", "t1", hist_msgs, _FakeRewriteLLM()
)
check(
    "rewrite_with_llm funciona com AIMessage (antes quebrava silenciosamente)",
    rewritten == "Quais as eletivas de BCC?",
    f"obteve {rewritten!r}",
)

print(f"\n{BOLD}── is_ambiguous_question ampliado (gatilho do LLM rewrite) ──{RESET}")
check("'algumas dessas eletivas' é ambígua",
      resolver.is_ambiguous_question("Tem como saber algumas dessas eletivas?"))
check("'E quais as disciplinas...?' (continuação com E) é ambígua",
      resolver.is_ambiguous_question("E quais as disciplinas obrigatórias no início?"))
check("pergunta auto-contida NÃO é ambígua",
      not resolver.is_ambiguous_question("Quais os pré-requisitos de Compiladores?"))
check("pergunta com sigla explícita NÃO é ambígua",
      not resolver.is_ambiguous_question("Quais as eletivas de BCC?"))

print(f"\n{BOLD}── LLM-first: termo do classificador ──{RESET}")
ic_mod = _import_module("src.intent_classifier", "src/intent_classifier.py")


class _FakeClassifyLLM:
    def __init__(self, payload):
        self._payload = payload

    def invoke(self, prompt):
        return _AIMessage(self._payload)


clf = ic_mod.IntentClassifier(None, llm=_FakeClassifyLLM('{"intent": "eletivas_curso", "term": "bcc"}'))
r = clf.classify("quais são as eletivas de bcc?")
check(
    "quick pattern + LLM concordam → resultado do LLM",
    r.intent == "eletivas_curso" and r.term == "bcc" and r.method == "llm",
    f"{r.intent}/{r.term}/{r.method}",
)
clf2 = ic_mod.IntentClassifier(None, llm=_FakeClassifyLLM('{"intent": "matriz_info", "term": "bcc"}'))
r2 = clf2.classify("quais são as eletivas de bcc?")
check(
    "LLM discorda do intent → intent do regex + TERMO do LLM",
    r2.intent == "eletivas_curso" and r2.term == "bcc" and r2.method == "regex+llm_term",
    f"{r2.intent}/{r2.term}/{r2.method}",
)
clf3 = ic_mod.IntentClassifier(None)
r3 = clf3.classify("quais são as eletivas de bcc?")
check(
    "sem LLM, fallback regex continua funcionando",
    r3.intent == "eletivas_curso" and r3.method == "regex",
    f"{r3.intent}/{r3.term}/{r3.method}",
)

print(f"\n{BOLD}── Herança de clarificação de curso (defeito T3) ──{RESET}")
t3 = cr_mod.ContextResolver()
T3_Q = "Quantas horas de eletivas?"
T3_CLARIF = (
    "De qual curso você quer ver as eletivas? "
    "Por exemplo: *eletivas de BCC* ou *eletivas do BCT*."
)
t3_hist = [
    {"role": "user", "content": T3_Q},
    {"role": "assistant", "content": T3_CLARIF},
]
for m in t3_hist:
    t3.update_context("t3", m["content"], m["role"])
t3_res, t3_mod = t3.resolve_question("do BCT", "t3", t3_hist)
check(
    "'do BCT' herda a pergunta pendente ('Quantas horas de eletivas?')",
    t3_mod and t3_res == "Quantas horas de eletivas do BCT?",
    f"obteve {t3_res!r}",
)
check(
    "contexto de curso atualizado para BCT",
    t3.get_context("t3").curso == "BCT",
    f"obteve {t3.get_context('t3').curso!r}",
)
t3b = cr_mod.ContextResolver()
for m in t3_hist:
    t3b.update_context("t3b", m["content"], m["role"])
t3b_res, t3b_mod = t3b.resolve_question("BCT", "t3b", t3_hist)
check(
    "'BCT' (sigla sozinha) também herda a pergunta pendente",
    t3b_mod and t3b_res == "Quantas horas de eletivas do BCT?",
    f"obteve {t3b_res!r}",
)
t3b.update_context("t3b", "BCT", "user")
check(
    "'BCT' como resposta de clarificação NÃO vira disciplina",
    t3b.get_context("t3b").disciplina is None,
    f"obteve {t3b.get_context('t3b').disciplina!r}",
)
t3c = cr_mod.ContextResolver()
t3c_hist = [
    {"role": "user", "content": "Quais as eletivas de BCC?"},
    {"role": "assistant", "content": "As eletivas de BCC são..."},
]
t3c_res, t3c_mod = t3c.resolve_question("do BCT", "t3c", t3c_hist)
check(
    "última pergunta JÁ tinha curso → 'do BCT' não é combinado",
    not t3c_mod,
    f"obteve {t3c_res!r}",
)
t3d = cr_mod.ContextResolver()
t3d_hist = [
    {"role": "user", "content": "obrigado"},
    {"role": "assistant", "content": "De nada!"},
]
t3d_res, t3d_mod = t3d.resolve_question("do BCT", "t3d", t3d_hist)
check(
    "última mensagem não era pergunta → 'do BCT' não é combinado",
    not t3d_mod,
    f"obteve {t3d_res!r}",
)

print(f"\n{BOLD}── Quebra de horas herda o curso do contexto (defeito T2) ──{RESET}")
t2 = cr_mod.ContextResolver()
T2_Q1 = "quantas horas para formar no BCT?"
T2_R1 = "Para integralizar o BCT são necessárias 2400 horas no total."
t2_hist = [
    {"role": "user", "content": T2_Q1},
    {"role": "assistant", "content": T2_R1},
]
for m in t2_hist:
    t2.update_context("t2", m["content"], m["role"])
t2_res, t2_mod = t2.resolve_question(
    "mas essas horas estão distribuídas em diferentes atividades?", "t2", t2_hist
)
check(
    "'essas horas estão distribuídas...?' herda o BCT",
    t2_mod and t2_res == (
        "Como as horas para integralizar o BCT estão distribuídas entre "
        "unidades curriculares, extensão e atividades complementares?"
    ),
    f"obteve {t2_res!r}",
)
t2_res2, t2_mod2 = t2.resolve_question("Quantas horas de eletivas?", "t2", t2_hist)
check(
    "'Quantas horas de eletivas?' com curso no contexto herda o BCT",
    t2_mod2 and t2_res2 == "Quantas horas de eletivas do BCT?",
    f"obteve {t2_res2!r}",
)
t2_res3, t2_mod3 = t2.resolve_question(
    "Quantas horas de eletivas do BCC?", "t2", t2_hist
)
check(
    "pergunta de horas com curso EXPLÍCITO não é reescrita",
    not t2_mod3,
    f"obteve {t2_res3!r}",
)

print(f"\n{BOLD}── Guard do humanizador (_kg_facts_preserved) ──{RESET}")
_stub_langgraph()
pipe_mod = _import_module("src.workflow.pipeline", "src/workflow/pipeline.py")
KG_MATRIZ = """**Matriz Curricular - Bacharelado Interdisciplinar em Ciência e Tecnologia:**

- **Sigla:** BCT
- **Duração:** 6 termos (semestres)
- **Carga Horária Total:** 2400 horas
- **Coordenador(a):** Profa. Dra. Marli Leite de Moraes
- **Vice-Coordenador(a):** Prof. Dr. João Marcos Batista Junior

O curso possui disciplinas obrigatórias organizadas por termo, além de eletivas nos Grupos 1, 2, 3 e eletivas extensionistas."""
BOA_PROSA = (
    "O BCT (sigla do Bacharelado Interdisciplinar em Ciência e Tecnologia) tem "
    "duração de 6 termos (semestres) e carga horária total de 2400 horas. A "
    "coordenação é da Profa. Dra. Marli Leite de Moraes, e o vice-coordenador é o "
    "Prof. Dr. João Marcos Batista Junior. O curso possui disciplinas "
    "obrigatórias organizadas por termo, além de eletivas nos Grupos 1, 2, 3 e "
    "eletivas extensionistas."
)
MUTILADA = (
    "O cursoisciplinas obrigatórias organizadas por termo, além de eletivas nos "
    "Grupos 1, 2, 3."
)
SEM_COORDENACAO = (
    "O BCT tem 6 termos e 2400 horas no total, com eletivas nos Grupos 1, 2 e 3."
)
check(
    "prosa fiel (bullets → texto corrido, fatos intactos) é aceita",
    pipe_mod._kg_facts_preserved(KG_MATRIZ, BOA_PROSA),
)
check(
    "saída mutilada (perde dígitos) é rejeitada",
    not pipe_mod._kg_facts_preserved(KG_MATRIZ, MUTILADA),
)
check(
    "saída que perde itens da lista (coordenação sumiu) é rejeitada",
    not pipe_mod._kg_facts_preserved(KG_MATRIZ, SEM_COORDENACAO),
)
check(
    "saída vazia é rejeitada",
    not pipe_mod._kg_facts_preserved(KG_MATRIZ, "  "),
)
check(
    "resposta sem números nem listas passa direto",
    pipe_mod._kg_facts_preserved("O coordenador é a Profa. Marli.", "Quem coordena é a Profa. Marli!"),
)

print(f"\n{BOLD}── Humanizador do KG com continuidade ──{RESET}")
pipeline_src = (ROOT / "src/workflow/pipeline.py").read_text()
check(
    "humanize_kg_response aceita history",
    "def humanize_kg_response(llm, question: str, kg_response: str, history: str = \"\")" in pipeline_src,
)
check(
    "humanizador tem regra de não re-saudação",
    "NAO cumprimente de novo" in pipeline_src,
)
check(
    "atalho simbólico passa o history ao humanizador",
    'history=state.get("history", "")' in pipeline_src,
)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
