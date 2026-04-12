"""
MultiAgentRAG — Entry point do sistema multi-agente FESP-AI.

Substitui o uso direto de RAGUnifesp.query() pela pipeline LangGraph,
mantendo compatibilidade total com a API existente.
"""

from typing import Dict, Optional, List
from .rag import RAGUnifesp
from .config import Config


class MultiAgentRAG:
    """
    Wrapper sobre RAGUnifesp que adiciona a camada multi-agente via LangGraph.

    A lógica de sincronização, Knowledge Graph e embeddings é idêntica ao RAGUnifesp.
    A diferença está no método `query()`, que agora roteia para agentes especializados.
    """

    # Metadados dos agentes para o frontend
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
        "fallback": {
            "label": "Assistente Geral",
            "description": "Assistente geral UNIFESP ICT",
            "color": "#6b7280",
            "icon": "Bot",
        },
        "symbolic_kg": {
            "label": "Knowledge Graph",
            "description": "Resposta direta do Knowledge Graph — sem LLM, 0% alucinação",
            "color": "#0ea5e9",
            "icon": "Network",
        },
    }

    def __init__(self, config: Config = None):
        self.config = config or Config()
        # RAGUnifesp contém toda a infra (LLM, embeddings, vector store, grafo)
        self._rag = RAGUnifesp(config=self.config)
        self._pipeline = None
        # Expor atributos necessários para compatibilidade com api.py
        self.llm = None
        self.chain = None
        self.knowledge_graph = None
        self.graph_rag = None
        self.relation_extractor = None
        self.graph_enricher = None

    def sync(self, force: bool = False) -> bool:
        """Inicializa o RAG e constrói a pipeline multi-agente."""
        result = self._rag.sync(force=force)

        # Sincronizar atributos públicos
        self.llm = self._rag.llm
        self.chain = self._rag.chain
        self.knowledge_graph = self._rag.knowledge_graph
        self.graph_rag = self._rag.graph_rag
        self.relation_extractor = self._rag.relation_extractor
        self.graph_enricher = self._rag.graph_enricher

        # Construir pipeline LangGraph
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

    def query(self, question: str) -> str:
        """
        Processa a pergunta pelo sistema multi-agente.
        Retorna apenas o texto da resposta (compatibilidade com api.py).
        """
        result = self.query_with_metadata(question)
        return result["response"]

    def query_with_metadata(self, question: str) -> Dict:
        """
        Processa a pergunta e retorna resposta + metadados do agente ativo.
        """
        if not self._pipeline:
            # Fallback para RAG original se pipeline não disponível
            response = self._rag.query(question)
            return {
                "response": response,
                "active_agent": "fallback",
                "agent_metadata": self.AGENT_METADATA["fallback"],
            }

        # Estado inicial
        initial_state = {
            "question": question,
            "enhanced_question": question,
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
            final_state = self._pipeline.invoke(initial_state)
            active_agent = final_state.get("active_agent", "fallback")

            return {
                "response": final_state.get("response", ""),
                "active_agent": active_agent,
                "intent": final_state.get("intent", "unknown"),
                "term": final_state.get("term", ""),
                "confidence": final_state.get("confidence", 0.0),
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

    # ── Métodos de compatibilidade com RAGUnifesp ──────────────────────────

    def list_sources(self) -> Dict[str, int]:
        return self._rag.list_sources()

    def extract_relations(self, text: str, min_confidence: float = 0.6) -> List[Dict]:
        return self._rag.extract_relations(text, min_confidence)

    def enrich_graph_from_text(self, text: str, min_confidence: float = 0.7) -> Dict:
        return self._rag.enrich_graph_from_text(text, min_confidence)
