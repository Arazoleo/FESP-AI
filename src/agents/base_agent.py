"""
Classe base para todos os agentes especializados do FESP-AI.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


class BaseAgent(ABC):
    """
    Agente base com interface comum para todos os agentes especializados.
    Cada agente encapsula:
    - Retrieval especializado (sabe onde buscar)
    - Prompt especializado (sabe como formatar)
    - Geração de resposta contextual com camada neurossimbólica
    """

    name: str = "base"
    description: str = ""
    color: str = "#6b7280"  # Cor para o indicador no frontend

    def __init__(self, rag_instance):
        self.rag = rag_instance
        self.llm = rag_instance.llm
        self.db = rag_instance.db
        self.knowledge_graph = rag_instance.knowledge_graph
        self.graph_rag = rag_instance.graph_rag

        # Camada neurossimbólica: validador simbólico baseado no Knowledge Graph
        self.validator = None
        if self.knowledge_graph is not None:
            try:
                from ..neurosymbolic_validator import SymbolicValidator
                self.validator = SymbolicValidator(self.knowledge_graph, llm=self.llm)
            except Exception:
                pass  # Não bloquear inicialização se validator falhar

    @abstractmethod
    def retrieve(self, question: str, intent: str, term: str) -> str:
        """Recupera contexto relevante para a pergunta."""
        pass

    @abstractmethod
    def get_prompt_template(self) -> str:
        """Retorna o template de prompt especializado deste agente."""
        pass

    def answer(self, question: str, intent: str, term: str) -> Dict[str, Any]:
        """
        Pipeline neurossimbólico completo:
          1. Retrieval (vector + KG)
          2. Enriquecimento simbólico: fatos verificados do KG → contexto (Simbólico → Neural)
          3. Geração pelo LLM com contexto enriquecido
          4. Validação simbólica: checar resposta contra KG (Neural → Simbólico)
        """
        context = self.retrieve(question, intent, term)

        # Guardrail: não invocar o LLM se não há contexto relevante.
        if not context or not context.strip():
            return {
                "response": (
                    "Não encontrei informações sobre isso na base de dados da UNIFESP ICT. "
                    "Tente reformular a pergunta, ser mais específico, ou consulte o site "
                    "oficial em unifesp.br."
                ),
                "agent": self.name,
                "agent_description": self.description,
                "context_length": 0,
                "context": "",
                "sources": [],
            }

        # ── Simbólico → Neural: enriquecer contexto com fatos verificados do KG ──
        enriched_context = context
        if self.validator and term and intent not in ("", "unknown"):
            kg_enrichment = self.validator.enrich_agent_context(intent, term)
            if kg_enrichment:
                enriched_context = kg_enrichment + "\n\n" + context

        template = self.get_prompt_template()
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()

        response = chain.invoke({"context": enriched_context, "question": question})

        # ── Neural → Simbólico: validar resposta gerada contra o KG ──────────
        if self.validator and intent not in ("", "unknown"):
            validation = self.validator.validate_response(response, intent, term)
            annotation = validation.to_annotation()
            if annotation:
                response += annotation

        sources = self._extract_sources_from_context(enriched_context)
        return {
            "response": response,
            "agent": self.name,
            "agent_description": self.description,
            "context_length": len(enriched_context),
            "context": enriched_context,
            "sources": sources,
        }

    def _format_docs(self, docs) -> str:
        """Formata documentos do vector store para o contexto."""
        parts = []
        for doc in docs:
            tipo = doc.metadata.get("tipo_documento", "documento")
            if tipo == "disciplina":
                header = f"[Disciplina: {doc.metadata.get('disciplina', 'N/A')} - {doc.metadata.get('secao', '')}]"
            else:
                header = f"[{doc.metadata.get('documento', 'Documento')} - {doc.metadata.get('secao', '')}]"
            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)

    def _get_graph_context(self, intent: str, term: str) -> Optional[str]:
        """Consulta o Knowledge Graph para o intent e termo dados."""
        if not self.graph_rag:
            return None
        try:
            return self.graph_rag.query_graph(intent, term)
        except Exception:
            return None

    def _extract_sources_from_context(self, context: str) -> List[str]:
        """
        Extrai "sources" do contexto formatado.

        Convenção atual do projeto:
        - trechos do vector store vêm com headers entre colchetes: `[Disciplina: ... - secao]` ou `[Documento - secao]`
        - trechos do KG normalmente incluem blocos textuais sem header padronizado
        """
        if not context:
            return []
        headers = re.findall(r"^\[([^\]]+)\]\s*$", context, flags=re.MULTILINE)
        cleaned = []
        for h in headers:
            s = re.sub(r"\s+", " ", h).strip()
            if s:
                cleaned.append(s)
        # manter ordem e remover duplicatas
        seen = set()
        uniq = []
        for s in cleaned:
            if s in seen:
                continue
            seen.add(s)
            uniq.append(s)
        return uniq
