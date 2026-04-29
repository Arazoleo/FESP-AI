"""
LangGraph pipeline para o sistema multi-agente FESP-AI.

Fluxo:
  router_node → [disciplinas | docentes | cursos | regimentos | fallback] → END
"""

from typing import Any
from langgraph.graph import StateGraph, END

from .state import AgentState
from .router import (
    route_intent,
    get_meta_capability_response,
    CURSOS_SEQ_KEYWORDS,
    REGIMENTO_FORCE_KEYWORDS,
    SYMBOLIC_DIRECT_INTENTS,
)
from .embedding_router import EmbeddingAgentRouter
from ..agents.disciplinas_agent import DisciplinasAgent
from ..agents.docentes_agent import DocentesAgent
from ..agents.cursos_agent import CursosAgent
from ..agents.regimentos_agent import RegimentosAgent


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

        intent = "unknown"
        term = ""
        confidence = 0.0

        # 1) Roteamento por embeddings (genérico): se confiança acima do limiar, usa
        active_agent = ""
        if embedding_router:
            active_agent, emb_conf = embedding_router.route(question)
            if active_agent:
                confidence = emb_conf
        # Correção: "me fale sobre matemática discreta" não é sobre professor
        if active_agent == "docentes" and (
            "fale sobre" in question_lower or "me fale sobre" in question_lower
        ) and "professor" not in question_lower and "docente" not in question_lower:
            active_agent = "disciplinas"

        # Overrides por keywords (têm prioridade sobre embedding quando presentes)
        if any(kw in question_lower for kw in CURSOS_SEQ_KEYWORDS):
            active_agent = "cursos"
        elif any(kw in question_lower for kw in REGIMENTO_FORCE_KEYWORDS):
            active_agent = "regimentos"

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
                    detected_term
                    and detected_intent in SYMBOLIC_DIRECT_INTENTS
                    and rag_instance.graph_rag
                ):
                    kg_response = rag_instance.graph_rag.query_graph(
                        detected_intent, detected_term
                    )
                    if kg_response:
                        return {
                            **state,
                            "response": kg_response,
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
                # Se active_agent != routed, mantém o agente do embedding e intent/term ficam como estão
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
            question, state.get("intent", ""), state.get("term", "")
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
            question, state.get("intent", ""), state.get("term", "")
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
            question, state.get("intent", ""), state.get("term", "")
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
            question, state.get("intent", ""), state.get("term", "")
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "regimentos",
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
            "fallback": "fallback",
            "meta": "meta",
            "symbolic_kg": "symbolic_kg",
        },
    )

    for agent_name in ["disciplinas", "docentes", "cursos", "regimentos", "fallback", "meta", "symbolic_kg"]:
        graph.add_edge(agent_name, END)

    return graph.compile()
