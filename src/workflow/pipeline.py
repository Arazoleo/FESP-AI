"""
LangGraph pipeline para o sistema multi-agente FESP-AI.

Fluxo:
  router_node → [disciplinas | docentes | cursos | regimentos | fallback] → END
"""

from typing import Any
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .state import AgentState
from .router import (
    route_intent,
    phrase_override,
    get_meta_capability_response,
    is_conversational,
    is_montar_grade,
    is_noticias,
    is_web_sjc,
    is_course_overview,
    SYMBOLIC_DIRECT_INTENTS,
)

# Intents que o KG pode responder sem nenhum termo (ou com termo vazio)
_TERM_OPTIONAL_INTENTS: frozenset = frozenset({"listar_cursos", "critical_disciplines"})
from .embedding_router import EmbeddingAgentRouter
from ..agents.disciplinas_agent import DisciplinasAgent
from ..agents.docentes_agent import DocentesAgent
from ..agents.cursos_agent import CursosAgent
from ..agents.regimentos_agent import RegimentosAgent
from ..agents.conversa_agent import ConversaAgent
from ..agents.montar_grade_agent import MontarGradeAgent
from ..agents.noticias_agent import NoticiasAgent
from ..agents.web_sjc_agent import WebSjcAgent


# Prompt do "humanizer" do symbolic_kg: suaviza o tom SEM alterar os fatos.
_KG_HUMANIZER_TEMPLATE = """Voce e o assistente virtual da UNIFESP ICT, simpatico e acolhedor. Abaixo esta uma RESPOSTA JA VERIFICADA, extraida diretamente da base de dados oficial. Ela esta correta e completa.

Pergunta do aluno: {question}

Resposta verificada:
{kg_response}

Sua tarefa: reescrever essa resposta num tom mais conversacional, caloroso e natural, como um chatbot amigavel conversando com um aluno.

REGRAS INVIOLAVEIS:
- NAO altere, remova, adicione ou invente NENHUM fato: nomes, codigos, numeros, disciplinas, professores, artigos e listas devem permanecer IDENTICOS em conteudo.
- Mantenha TODOS os itens de qualquer lista, na mesma ordem.
- Voce so pode mudar a FORMA: uma abertura amigavel, conectar as frases de modo natural e, se fizer sentido, uma frase final se colocando a disposicao.
- Responda em PORTUGUES BRASILEIRO, de forma breve. NAO use emojis.
- Nao comente estas instrucoes nem mencione "base de dados" ou "Knowledge Graph".

Resposta conversacional:"""


def humanize_kg_response(llm, question: str, kg_response: str, history: str = "") -> str:
    """
    Suaviza o tom de uma resposta determinística do KG via LLM, preservando os
    fatos. Em caso de erro, retorna a resposta original (degradação segura).
    Só deve ser chamada quando Config.HUMANIZE_KG está ativo.

    `history`: trocas anteriores — evita re-saudação ("Olá!") a cada turno.
    """
    if not llm or not kg_response or not kg_response.strip():
        return kg_response
    try:
        template = _KG_HUMANIZER_TEMPLATE
        inputs = {"question": question, "kg_response": kg_response}
        if history:
            template = template.replace(
                "Pergunta do aluno: {question}",
                "HISTORICO RECENTE DA CONVERSA:\n{history}\n\n"
                "A conversa JA ESTA EM ANDAMENTO: NAO cumprimente de novo "
                "(nada de 'Ola', 'Oi'); emende direto no assunto.\n\n"
                "Pergunta do aluno: {question}",
                1,
            )
            inputs["history"] = history
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()
        softened = chain.invoke(inputs)
        return softened.strip() or kg_response
    except Exception:
        return kg_response


def build_pipeline(rag_instance):
    """
    Constrói e compila o LangGraph com os agentes especializados.

    Args:
        rag_instance: instância de RAGUnifesp já inicializada (sync() chamado)

    Returns:
        Compiled LangGraph app
    """
    # Instanciar agentes com acesso ao rag
    agents = {
        "disciplinas": DisciplinasAgent(rag_instance),
        "docentes": DocentesAgent(rag_instance),
        "cursos": CursosAgent(rag_instance),
        "regimentos": RegimentosAgent(rag_instance),
        "conversa": ConversaAgent(rag_instance),
        "montar_grade": MontarGradeAgent(rag_instance),
        "noticias": NoticiasAgent(rag_instance),
        "web_sjc": WebSjcAgent(rag_instance),
    }

    # Roteador por embeddings (prioridade sobre intent/keywords quando confiança alta)
    embedding_router = None
    if getattr(rag_instance, "_rag", None) and getattr(rag_instance._rag, "embeddings", None):
        embedding_router = EmbeddingAgentRouter(rag_instance._rag.embeddings, confidence_threshold=0.58)
        embedding_router.initialize()

    # ── Nó: Router ──────────────────────────────────────────────────────────
    def router_node(state: AgentState) -> AgentState:
        """Classifica a intent e decide qual agente chamar."""
        question = state.get("enhanced_question") or state.get("question", "")
        question_lower = question.lower()

        # Perguntas meta sobre capacidades do sistema → resposta fixa
        meta_response = get_meta_capability_response(question_lower)
        if meta_response:
            return {
                **state,
                "response": meta_response,
                "active_agent": "meta",
            }

        # Conversa social (saudações, agradecimentos, despedidas, identidade) →
        # agente conversacional, antes do roteamento por embeddings/intent.
        if is_conversational(question_lower):
            return {
                **state,
                "intent": "conversa",
                "term": "",
                "confidence": 1.0,
                "active_agent": "conversa",
            }

        # Pedido de montar a grade / planejar trajetória → agente dedicado.
        if is_montar_grade(question_lower):
            return {
                **state,
                "intent": "plan_curriculum",
                "term": "",
                "confidence": 1.0,
                "active_agent": "montar_grade",
            }

        # Pedido de notícias / novidades da UNIFESP → agente de notícias.
        if is_noticias(question_lower):
            return {
                **state,
                "intent": "noticias",
                "term": "",
                "confidence": 1.0,
                "active_agent": "noticias",
            }

        # Pergunta institucional sobre o campus → agente do site (cobertura completa).
        if is_web_sjc(question_lower):
            return {
                **state,
                "intent": "web_sjc",
                "term": "",
                "confidence": 1.0,
                "active_agent": "web_sjc",
            }

        # Pergunta descritiva sobre um CURSO ("O que é o BCT?") → página do curso
        # no site. Desambiguação simbólica via KG: se a entidade fosse uma
        # disciplina ("O que é Teoria dos Grafos?"), segue o fluxo normal.
        if is_course_overview(question_lower, rag_instance.knowledge_graph):
            return {
                **state,
                "intent": "web_sjc",
                "term": "",
                "confidence": 0.9,
                "active_agent": "web_sjc",
            }

        intent = "unknown"
        term = ""
        confidence = 0.0

        # 1) Roteamento por embeddings (genérico): se confiança acima do limiar, usa
        active_agent = ""
        if embedding_router:
            active_agent, emb_conf = embedding_router.route(question)
            if active_agent:
                confidence = emb_conf
        # Overrides de alta precisão por frase (prioridade sobre o embedding).
        # Fonte única em router.phrase_override — substitui as correções
        # hardcoded pontuais que existiam aqui.
        override = phrase_override(question_lower, active_agent)
        if override:
            active_agent = override

        # 2) Intent/term do GraphRAG (para preencher intent/term quando agente é docentes ou ainda não definido)
        if rag_instance.graph_rag:
            use_graph, detected_intent, detected_term = (
                rag_instance.graph_rag.should_use_graph(question)
            )
            if use_graph and detected_intent:
                # ── Atalho Neurossimbólico ────────────────────────────────────
                # Para intents determinísticos, o KG responde diretamente sem LLM.
                # Isso elimina latência de inferência e risco de alucinação.
                if (
                    (detected_term or detected_intent in _TERM_OPTIONAL_INTENTS)
                    and detected_intent in SYMBOLIC_DIRECT_INTENTS
                    and rag_instance.graph_rag
                ):
                    kg_response = rag_instance.graph_rag.query_graph(
                        detected_intent, detected_term
                    )
                    if kg_response:
                        # Humanização opcional: suaviza o tom sem alterar os fatos.
                        # Desligada por padrão (paper puro); ative com FESPAI_HUMANIZE_KG=1.
                        response_text = kg_response
                        if getattr(rag_instance.config, "HUMANIZE_KG", False):
                            response_text = humanize_kg_response(
                                rag_instance.llm, question, kg_response,
                                history=state.get("history", ""),
                            )
                        return {
                            **state,
                            "response": response_text,
                            "intent": detected_intent,
                            "term": detected_term,
                            "confidence": 1.0,
                            "active_agent": "symbolic_kg",
                            "context": kg_response,
                            "sources": ["Knowledge Graph"],
                        }
                # ── Roteamento normal para agentes ───────────────────────────
                routed = route_intent(detected_intent, question_lower)
                if not active_agent:
                    intent = detected_intent
                    term = detected_term or ""
                    confidence = 0.8
                    active_agent = routed
                elif active_agent == routed:
                    # Mesmo agente (ex.: docentes): preencher intent/term para o agente usar
                    intent = detected_intent
                    term = detected_term or ""
                    if confidence < 0.5:
                        confidence = 0.8
                else:
                    # Agente do embedding vence, mas intent/term detectados ainda
                    # são úteis para os lookups do agente (antes ficavam vazios)
                    if not term and detected_term:
                        intent = detected_intent
                        term = detected_term
        if not active_agent:
            active_agent = route_intent(intent, question_lower)

        return {
            **state,
            "intent": intent,
            "term": term,
            "confidence": confidence,
            "active_agent": active_agent,
        }

    # ── Nó: Agente de Disciplinas ────────────────────────────────────────────
    def disciplinas_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["disciplinas"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "disciplinas",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    # ── Nó: Agente de Docentes ────────────────────────────────────────────────
    def docentes_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["docentes"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "docentes",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    # ── Nó: Agente de Cursos ──────────────────────────────────────────────────
    def cursos_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["cursos"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "cursos",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    # ── Nó: Agente de Regimentos ──────────────────────────────────────────────
    def regimentos_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["regimentos"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "regimentos",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    # ── Nó: Agente Conversacional (saudações, agradecimentos, small talk) ─────
    def conversa_node(state: AgentState) -> AgentState:
        question = state.get("question", "")
        result = agents["conversa"].answer(question, "", "", history=state.get("history", ""))
        return {
            **state,
            "response": result["response"],
            "active_agent": "conversa",
            "context": "",
            "sources": [],
        }

    # ── Nó: Agente Montar Grade (planejador de trajetória) ────────────────────
    def montar_grade_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["montar_grade"].answer(question, state.get("intent", ""), "", history=state.get("history", ""))
        return {
            **state,
            "response": result["response"],
            "active_agent": "montar_grade",
            "context": "",
            "sources": [],
            "plan_request": result.get("plan_request"),
        }

    # ── Nó: Agente de Notícias (retrieval ao vivo, fonte oficial) ─────────────
    def noticias_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["noticias"].answer(question, state.get("intent", ""), "", history=state.get("history", ""))
        return {
            **state,
            "response": result["response"],
            "active_agent": "noticias",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    # ── Nó: Agente Web SJC (cobertura completa do site do campus) ─────────────
    def web_sjc_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["web_sjc"].answer(question, state.get("intent", ""), "", history=state.get("history", ""))
        return {
            **state,
            "response": result["response"],
            "active_agent": "web_sjc",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    # ── Nó: Fallback (RAG genérico) ───────────────────────────────────────────
    def fallback_node(state: AgentState) -> AgentState:
        """Fallback usa a lógica RAG original para perguntas não classificadas."""
        question = state.get("enhanced_question") or state.get("question", "")
        try:
            response = rag_instance.query(question)
        except Exception as e:
            response = f"Desculpe, não consegui processar sua pergunta: {e}"
        return {**state, "response": response, "active_agent": "fallback"}

    # ── Nó: Meta (resposta fixa para "você tem acesso a X?") ──────────────────
    def meta_node(state: AgentState) -> AgentState:
        return state

    # ── Nó: Symbolic KG (resposta direta do Knowledge Graph, sem LLM) ────────
    def symbolic_kg_node(state: AgentState) -> AgentState:
        """
        Nó neurossimbólico: a resposta já foi gerada diretamente pelo KG
        no router_node. Este nó é um pass-through para o END.
        Elimina latência de LLM e alucinações para consultas estruturais.
        """
        return state

    # ── Função de roteamento condicional ──────────────────────────────────────
    def select_agent(state: AgentState) -> str:
        agent = state.get("active_agent", "fallback")
        if agent in ("meta", "symbolic_kg"):
            return agent
        if agent in agents:
            return agent
        return "fallback"

    # ── Construir grafo ───────────────────────────────────────────────────────
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("disciplinas", disciplinas_node)
    graph.add_node("docentes", docentes_node)
    graph.add_node("cursos", cursos_node)
    graph.add_node("regimentos", regimentos_node)
    graph.add_node("conversa", conversa_node)
    graph.add_node("montar_grade", montar_grade_node)
    graph.add_node("noticias", noticias_node)
    graph.add_node("web_sjc", web_sjc_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("meta", meta_node)
    graph.add_node("symbolic_kg", symbolic_kg_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        select_agent,
        {
            "disciplinas": "disciplinas",
            "docentes": "docentes",
            "cursos": "cursos",
            "regimentos": "regimentos",
            "conversa": "conversa",
            "montar_grade": "montar_grade",
            "noticias": "noticias",
            "web_sjc": "web_sjc",
            "fallback": "fallback",
            "meta": "meta",
            "symbolic_kg": "symbolic_kg",
        },
    )

    for agent_name in ["disciplinas", "docentes", "cursos", "regimentos", "conversa", "montar_grade", "noticias", "web_sjc", "fallback", "meta", "symbolic_kg"]:
        graph.add_edge(agent_name, END)

    return graph.compile()
