"""
MultiAgentRAG - Entry point do sistema multi-agente FESP-AI.

Substitui o uso direto de RAGUnifesp.query() pela pipeline LangGraph,
mantendo compatibilidade total com a API existente.
"""

import os

from typing import Dict, Optional, List
from .rag import RAGUnifesp
from .config import Config


class MultiAgentRAG:
    """
    Wrapper sobre RAGUnifesp que adiciona a camada multi-agente via LangGraph.

    A lógica de sincronização, Knowledge Graph e embeddings é idêntica ao RAGUnifesp.
    A diferença está no método `query()`, que agora roteia para agentes especializados.
    """

    AGENT_METADATA = {
        "disciplinas": {
            "label": "Agente Disciplinas",
            "description": "Especialista em disciplinas, pré-requisitos e ementas",
            "color": "#10b981",
            "icon": "BookOpen",
        },
        "docentes": {
            "label": "Agente Docentes",
            "description": "Especialista em docentes, áreas e contatos",
            "color": "#8b5cf6",
            "icon": "Users",
        },
        "cursos": {
            "label": "Agente Cursos",
            "description": "Especialista em matrizes curriculares e estrutura dos cursos",
            "color": "#f59e0b",
            "icon": "GraduationCap",
        },
        "regimentos": {
            "label": "Agente Regimentos",
            "description": "Especialista em normas, regimentos e regulamentos",
            "color": "#ef4444",
            "icon": "FileText",
        },
        "conversa": {
            "label": "Assistente Conversacional",
            "description": "Saudações, agradecimentos e conversa do dia a dia",
            "color": "#22c55e",
            "icon": "MessageCircle",
        },
        "montar_grade": {
            "label": "Planejador de Trajetória",
            "description": "Monta sua grade semestre a semestre respeitando pré-requisitos",
            "color": "#a855f7",
            "icon": "Route",
        },
        "noticias": {
            "label": "Notícias UNIFESP",
            "description": "Notícias e novidades oficiais do campus (ao vivo)",
            "color": "#eab308",
            "icon": "Newspaper",
        },
        "web_sjc": {
            "label": "Site do Campus",
            "description": "Busca em qualquer página do site do campus SJC",
            "color": "#0ea5e9",
            "icon": "Globe",
        },
        "fallback": {
            "label": "Assistente Geral",
            "description": "Assistente geral UNIFESP ICT",
            "color": "#6b7280",
            "icon": "Bot",
        },
        "symbolic_kg": {
            "label": "Knowledge Graph",
            "description": "Resposta direta do Knowledge Graph - sem LLM, 0% alucinação",
            "color": "#0ea5e9",
            "icon": "Network",
        },
    }

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._rag = RAGUnifesp(config=self.config)
        self._pipeline = None
        self.llm = None
        self.chain = None
        self.knowledge_graph = None
        self.graph_rag = None
        self.relation_extractor = None
        self.graph_enricher = None

    def sync(self, force: bool = False) -> bool:
        """Inicializa o RAG e constrói a pipeline multi-agente."""
        result = self._rag.sync(force=force)

        self.llm = self._rag.llm
        self.chain = self._rag.chain
        self.knowledge_graph = self._rag.knowledge_graph
        self.graph_rag = self._rag.graph_rag
        self.relation_extractor = self._rag.relation_extractor
        self.graph_enricher = self._rag.graph_enricher

        if self.knowledge_graph is not None and getattr(self._rag, "embeddings", None):
            try:
                self.knowledge_graph.kgc.set_embeddings(self._rag.embeddings)
            except Exception:
                pass

        self._build_pipeline()

        return result

    def _build_pipeline(self):
        """Constrói a pipeline LangGraph com os agentes especializados."""
        try:
            from .workflow.pipeline import build_pipeline
            self._pipeline = build_pipeline(self._rag)
            print("Pipeline multi-agente inicializada!")
        except Exception as e:
            print(f"[MultiAgentRAG] Erro ao construir pipeline: {e}")
            self._pipeline = None

    def query(self, question: str, history: str = "") -> str:
        """
        Processa a pergunta pelo sistema multi-agente.
        Retorna apenas o texto da resposta (compatibilidade com api.py).
        """
        result = self.query_with_metadata(question, history=history)
        return result["response"]

    def query_with_metadata(
        self, question: str, history: str = "", original_question: str = None
    ) -> Dict:
        """
        Processa a pergunta e retorna resposta + metadados do agente ativo.

        `history`: últimas trocas formatadas ("Aluno: ...\nAssistente: ...") para
        continuidade de diálogo nos prompts dos agentes.
        `original_question`: pergunta como o aluno digitou (antes do
        ContextResolver) - registrada na fila de misses.
        """
        if not self._pipeline:
            response = self._rag.query(question)
            return {
                "response": response,
                "active_agent": "fallback",
                "agent_metadata": self.AGENT_METADATA["fallback"],
            }

        initial_state = {
            "question": question,
            "enhanced_question": question,
            "history": history,
            "active_agent": "fallback",
            "intent": "unknown",
            "term": "",
            "confidence": 0.0,
            "context": "",
            "response": "",
            "sources": [],
            "retry_count": 0,
        }

        try:
            from .workflow.second_chance import run_with_second_chance, is_miss_response
            from . import telemetry
            if os.getenv("FESPAI_SECOND_CHANCE", "1") == "0":
                final_state = self._pipeline.invoke(initial_state)
            else:
                final_state = run_with_second_chance(
                    self._pipeline.invoke, initial_state, telemetry.incr
                )
            if final_state.get("retry_from_agent"):
                print(
                    f"[SecondChance] retry recuperado: "
                    f"{final_state['retry_from_agent']} → "
                    f"{final_state.get('active_agent', '?')}"
                )
            active_agent = final_state.get("active_agent", "fallback")

            final_response = final_state.get("response", "")
            if is_miss_response(final_response):
                from .misses_queue import record_miss
                agentes = [active_agent]
                tried = final_state.get("retry_agent_tried")
                if tried and tried not in agentes:
                    agentes.append(tried)
                record_miss(
                    question=original_question or question,
                    enhanced_question=question,
                    agentes=agentes,
                    resposta=final_response,
                )
                telemetry.incr("miss_registrado")

            if final_response and not is_miss_response(final_response):
                from .atividades_complementares import maybe_append_offer
                offered = maybe_append_offer(
                    original_question or question, final_response
                )
                if offered != final_response:
                    final_state["response"] = offered
                    telemetry.incr("ac_offer_appended")

            from .followups import suggest_followups
            suggestions = suggest_followups(
                final_state.get("intent", ""),
                final_state.get("term", ""),
                final_state.get("response", ""),
            )

            return {
                "response": final_state.get("response", ""),
                "active_agent": active_agent,
                "intent": final_state.get("intent", "unknown"),
                "term": final_state.get("term", ""),
                "confidence": final_state.get("confidence", 0.0),
                "context": final_state.get("context", ""),
                "sources": final_state.get("sources", []),
                "plan_request": final_state.get("plan_request"),
                "graph_data": final_state.get("graph_data"),
                "list_data": final_state.get("list_data"),
                "suggestions": suggestions,
                "agent_metadata": self.AGENT_METADATA.get(
                    active_agent, self.AGENT_METADATA["fallback"]
                ),
            }
        except Exception as e:
            print(f"[MultiAgentRAG] Erro na pipeline: {e}")
            response = self._rag.query(question)
            return {
                "response": response,
                "active_agent": "fallback",
                "agent_metadata": self.AGENT_METADATA["fallback"],
            }


    def list_sources(self) -> Dict[str, int]:
        return self._rag.list_sources()

    def extract_relations(self, text: str, min_confidence: float = 0.6) -> List[Dict]:
        return self._rag.extract_relations(text, min_confidence)

    def enrich_graph_from_text(self, text: str, min_confidence: float = 0.7) -> Dict:
        return self._rag.enrich_graph_from_text(text, min_confidence)
