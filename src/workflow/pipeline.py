"""
LangGraph pipeline para o sistema multi-agente FESP-AI.

Fluxo:
  router_node → [disciplinas | docentes | cursos | regimentos | fallback] → END
"""

import os
import re
from collections import Counter
from typing import Any
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .state import AgentState
from .router import (
    route_intent,
    phrase_override,
    llm_route,
    term_from_llm_route,
    get_meta_capability_response,
    is_conversational,
    is_montar_grade,
    is_noticias,
    is_web_sjc,
    is_course_overview,
    is_regimento_domain,
    SYMBOLIC_DIRECT_INTENTS,
)
from ..telemetry import incr as telemetry_incr

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


def _kg_facts_preserved(original: str, humanized: str) -> bool:
    """
    Guard barato de pós-verificação do humanizer: True se a saída preservou os
    fatos da resposta original do KG. O LLM ocasionalmente mutila a resposta
    (ex.: "O cursoisciplinas obrigatórias" - perda de um trecho no decoding).

    Critérios (perda > 10% → descarta):
      - dígitos: >= 90% dos tokens numéricos da original (multiset) presentes;
      - listas: com 3+ itens na original, >= 90% dos itens com o CONTEÚDO
        presente na saída (o humanizer pode converter bullets em prosa - o que
        conta é o conteúdo do item, não o marcador).
    """
    if not humanized or not humanized.strip():
        return False
    orig_nums = re.findall(r"\d+", original)
    if orig_nums:
        hum_counts = Counter(re.findall(r"\d+", humanized))
        kept = sum(
            min(count, hum_counts.get(num, 0))
            for num, count in Counter(orig_nums).items()
        )
        if kept < 0.9 * len(orig_nums):
            return False
    orig_items = re.findall(r"^\s*(?:[-•*]|\d+[.)])\s+(.+)$", original, re.MULTILINE)
    if len(orig_items) >= 3:
        hum_lower = humanized.lower()
        items_ok = 0
        for item in orig_items:
            tokens = re.findall(r"[^\W\d_]{4,}", item, re.UNICODE)
            if not tokens:
                items_ok += 1
                continue
            present = sum(1 for t in tokens if t.lower() in hum_lower)
            if present >= 0.6 * len(tokens):
                items_ok += 1
        if items_ok < 0.9 * len(orig_items):
            return False
    return True


def humanize_kg_response(llm, question: str, kg_response: str, history: str = "") -> str:
    """
    Suaviza o tom de uma resposta determinística do KG via LLM, preservando os
    fatos. Em caso de erro, retorna a resposta original (degradação segura).
    Só deve ser chamada quando Config.HUMANIZE_KG está ativo.

    `history`: trocas anteriores - evita re-saudação ("Olá!") a cada turno.
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
        softened = chain.invoke(inputs).strip()
        if not _kg_facts_preserved(kg_response, softened):
            return kg_response
        return softened
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

    embedding_router = None
    if getattr(rag_instance, "_rag", None) and getattr(rag_instance._rag, "embeddings", None):
        embedding_router = EmbeddingAgentRouter(rag_instance._rag.embeddings, confidence_threshold=0.58)
        embedding_router.initialize()

    def router_node(state: AgentState) -> AgentState:
        """Classifica a intent e decide qual agente chamar."""
        question = state.get("enhanced_question") or state.get("question", "")
        question_lower = question.lower()

        forced = state.get("forced_agent")
        if forced and (forced in agents or forced == "fallback"):
            return {**state, "active_agent": forced}

        meta_response = get_meta_capability_response(question_lower)
        if meta_response:
            return {
                **state,
                "response": meta_response,
                "active_agent": "meta",
            }

        from ..atividades_complementares import (
            is_ac_question,
            is_breakdown_request,
            build_breakdown_response,
        )
        if is_breakdown_request(question):
            ac_response = build_breakdown_response()
            if ac_response:
                telemetry_incr("ac_breakdown_direct")
                return {
                    **state,
                    "response": ac_response,
                    "intent": "ac_breakdown",
                    "term": "",
                    "confidence": 1.0,
                    "active_agent": "symbolic_kg",
                    "context": ac_response,
                    "sources": ["Regulamento de Atividades Complementares do BCT (2023)"],
                }

        if is_ac_question(question):
            telemetry_incr("ac_routed_regimentos")
            return {
                **state,
                "intent": "faqs",
                "term": "",
                "confidence": 0.95,
                "active_agent": "regimentos",
            }

        if is_regimento_domain(question_lower):
            telemetry_incr("regimento_domain_direct")
            return {
                **state,
                "intent": "faqs",
                "term": "",
                "confidence": 0.9,
                "active_agent": "regimentos",
            }

        if is_conversational(question_lower):
            return {
                **state,
                "intent": "conversa",
                "term": "",
                "confidence": 1.0,
                "active_agent": "conversa",
            }

        if is_montar_grade(question_lower):
            return {
                **state,
                "intent": "plan_curriculum",
                "term": "",
                "confidence": 1.0,
                "active_agent": "montar_grade",
            }

        if is_noticias(question_lower):
            return {
                **state,
                "intent": "noticias",
                "term": "",
                "confidence": 1.0,
                "active_agent": "noticias",
            }

        if is_web_sjc(question_lower):
            return {
                **state,
                "intent": "web_sjc",
                "term": "",
                "confidence": 1.0,
                "active_agent": "web_sjc",
            }

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
        active_agent = ""

        detected_intent, detected_term = "", ""
        if rag_instance.graph_rag:
            use_graph, di, dt = rag_instance.graph_rag.should_use_graph(question)
            if use_graph and di:
                detected_intent, detected_term = di, dt or ""
                if (
                    (detected_term or detected_intent in _TERM_OPTIONAL_INTENTS)
                    and detected_intent in SYMBOLIC_DIRECT_INTENTS
                ):
                    kg_response = rag_instance.graph_rag.query_graph(
                        detected_intent, detected_term
                    )
                    if kg_response:
                        graph_data = None
                        if detected_intent in (
                            "prerequisite_chain", "dependents",
                            "trajectory_planning", "recommended_before",
                        ):
                            try:
                                graph_data = rag_instance.graph_rag.graph_payload(
                                    detected_intent, detected_term
                                )
                            except Exception:
                                graph_data = None
                        list_data = None
                        if detected_intent in ("eletivas_curso", "disciplinas_termo"):
                            list_data = rag_instance.graph_rag.list_payload(
                                detected_intent, detected_term
                            )
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
                            "graph_data": graph_data,
                            "list_data": list_data,
                        }

        emb_agent, emb_conf = "", 0.0
        if embedding_router:
            emb_agent, emb_conf = embedding_router.route(question)

        override = phrase_override(question_lower, emb_agent)
        if override:
            active_agent = override
            confidence = max(emb_conf, 0.9)
        else:
            routed_llm = None
            if os.getenv("FESPAI_LLM_ROUTE", "1") != "0":
                routed_llm = llm_route(
                    question,
                    state.get("history", ""),
                    rag_instance.knowledge_graph,
                    rag_instance.llm,
                    telemetry_incr=telemetry_incr,
                )
            if routed_llm:
                active_agent = routed_llm["agente"]
                confidence = 0.85
                if routed_llm.get("intent"):
                    intent = routed_llm["intent"]
                term = term_from_llm_route(routed_llm)
                telemetry_incr("llm_route_decisor")
            elif emb_agent:
                active_agent = emb_agent
                confidence = emb_conf
                telemetry_incr("llm_route_fallback_embedding")

        if detected_intent and intent == "unknown":
            intent = detected_intent
        if detected_term and not term:
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

    def fallback_node(state: AgentState) -> AgentState:
        """Fallback usa a lógica RAG original para perguntas não classificadas."""
        question = state.get("enhanced_question") or state.get("question", "")
        try:
            response = rag_instance.query(question)
        except Exception as e:
            response = f"Desculpe, não consegui processar sua pergunta: {e}"
        return {**state, "response": response, "active_agent": "fallback"}

    def meta_node(state: AgentState) -> AgentState:
        return state

    def symbolic_kg_node(state: AgentState) -> AgentState:
        """
        Nó neurossimbólico: a resposta já foi gerada diretamente pelo KG
        no router_node. Este nó é um pass-through para o END.
        Elimina latência de LLM e alucinações para consultas estruturais.
        """
        return state

    def select_agent(state: AgentState) -> str:
        agent = state.get("active_agent", "fallback")
        if agent in ("meta", "symbolic_kg"):
            return agent
        if agent in agents:
            return agent
        return "fallback"

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
