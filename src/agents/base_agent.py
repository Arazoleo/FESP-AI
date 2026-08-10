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
    color: str = "#6b7280"

    GOLDEN_RULE: str = (
        "⚠️ REGRA DE OURO: Voce so pode usar informacoes que aparecem LITERALMENTE no CONTEXTO abaixo.\n"
        "Nao use conhecimento proprio, nao invente nomes, codigos, emails, salas, cargas horarias, "
        "docentes, ementas ou regras.\n"
        "Se a informacao NAO estiver no CONTEXTO, diga com gentileza que nao tem esse dado na base da UNIFESP ICT."
    )

    _PRONOUN_WORDS: frozenset = frozenset({
        'ela', 'ele', 'elas', 'eles', 'dela', 'dele', 'delas', 'deles',
        'isso', 'esta', 'este', 'essa', 'esse', 'disso', 'ementa', 'ementas',
        'essa disciplina', 'este professor', 'essa matéria',
    })

    _CLARIFICATION_FOR_INTENT: Dict[str, str] = {
        "ementa_disciplina":    "Sobre qual disciplina você quer ver a ementa?",
        "prerequisite_chain":   "Qual é a disciplina cujos pré-requisitos você quer conhecer?",
        "dependents":           "Qual disciplina você quer saber quais outras dependem dela?",
        "discipline_docentes":  "De qual disciplina você quer saber os docentes?",
        "unlocked_disciplines": (
            "Quais disciplinas você já cursou? "
            "Exemplo: *Algoritmos e Estruturas de Dados I, Cálculo 1*."
        ),
        "docente_info":         "Qual é o nome do professor que você quer consultar?",
        "docente_areas":        "Qual é o nome do professor?",
        "docente_disciplines":  "Qual é o nome do professor?",
        "docentes_by_area":     "Qual área de pesquisa você quer buscar?",
    }

    def __init__(self, rag_instance):
        self.rag = rag_instance
        self.llm = rag_instance.llm
        self.db = rag_instance.db
        self.knowledge_graph = rag_instance.knowledge_graph
        self.graph_rag = rag_instance.graph_rag

        self.validator = None
        if self.knowledge_graph is not None:
            try:
                from ..neurosymbolic_validator import SymbolicValidator
                self.validator = SymbolicValidator(self.knowledge_graph, llm=self.llm)
            except Exception:
                pass

    @abstractmethod
    def retrieve(self, question: str, intent: str, term: str) -> str:
        """Recupera contexto relevante para a pergunta."""
        pass

    @abstractmethod
    def get_prompt_template(self) -> str:
        """Retorna o template de prompt especializado deste agente."""
        pass

    def _is_empty_term(self, term: str) -> bool:
        """Retorna True se o termo é vazio ou apenas pronomes/demonstrativos."""
        if not term or term in ("", "unknown"):
            return True
        words = set(term.lower().split())
        return words.issubset(self._PRONOUN_WORDS)

    def _expand_via_kg(self, term: str, tipo: str = "disciplina") -> Optional[str]:
        """Se o termo é sigla ou código, expande para o nome completo do KG."""
        if not term or not self.knowledge_graph:
            return None
        try:
            node_id = self.knowledge_graph._find_node(term, tipo)
            if node_id:
                nome = self.knowledge_graph.graph.nodes[node_id].get("nome", "")
                if nome and nome.strip().lower() != term.strip().lower():
                    return nome
        except Exception:
            pass
        return None

    _HISTORY_BLOCK = (
        "HISTORICO RECENTE DA CONVERSA (apenas para continuidade de dialogo - "
        "NAO e fonte de fatos; fatos vem so do CONTEXTO):\n{history}\n\n"
        "REGRA DE CONTINUIDADE: a conversa JA ESTA EM ANDAMENTO. NAO cumprimente "
        "de novo (nada de 'Ola', 'Oi', 'Tudo bem?'). Responda direto, como quem "
        "continua um papo, e nao repita o que ja foi dito.\n\n"
        "Pergunta: {question}"
    )

    def _apply_history(self, template: str, history: str) -> str:
        """
        Insere o histórico recente + regra de continuidade antes da pergunta.
        Sem histórico (primeira mensagem), o template fica intacto - e o agente
        pode abrir com a saudação de praxe.
        """
        if not history:
            return template
        return template.replace("Pergunta: {question}", self._HISTORY_BLOCK, 1)

    def answer(self, question: str, intent: str, term: str, history: str = "") -> Dict[str, Any]:
        """
        Pipeline neurossimbólico completo:
          1. Retrieval (vector + KG)
          2. Enriquecimento simbólico: fatos verificados do KG → contexto (Simbólico → Neural)
          3. Geração pelo LLM com contexto enriquecido
          4. Validação simbólica: checar resposta contra KG (Neural → Simbólico)

        `history` (opcional): últimas trocas da conversa, injetadas no prompt
        para continuidade de diálogo (sem re-saudação a cada turno).
        """
        if self._is_empty_term(term) and intent in self._CLARIFICATION_FOR_INTENT:
            return {
                "response": self._CLARIFICATION_FOR_INTENT[intent],
                "agent": self.name,
                "agent_description": self.description,
                "context_length": 0,
                "context": "",
                "sources": [],
            }

        context = self.retrieve(question, intent, term)

        if not context or not context.strip():
            suggestion = self._kgc_suggestion(term)
            response_text = (
                suggestion if suggestion else
                "Não encontrei informações sobre isso na base de dados da UNIFESP ICT. "
                "Tente reformular a pergunta, ser mais específico, ou consulte o site "
                "oficial em unifesp.br."
            )
            return {
                "response": response_text,
                "agent": self.name,
                "agent_description": self.description,
                "context_length": 0,
                "context": "",
                "sources": [],
            }

        enriched_context = context
        if self.validator and term and intent not in ("", "unknown"):
            kg_enrichment = self.validator.enrich_agent_context(intent, term)
            if kg_enrichment:
                enriched_context = kg_enrichment + "\n\n" + context

        template = self._apply_history(self.get_prompt_template(), history)
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()

        inputs = {"context": enriched_context, "question": question}
        if history:
            inputs["history"] = history
        response = chain.invoke(inputs)

        if self.validator and intent not in ("", "unknown"):
            response, _ = self.validator.validate_and_correct(response, intent, term)

        _NO_INFO_MARKERS = ("Nao tenho essa informacao", "não tenho essa informação")
        if any(m.lower() in response.lower() for m in _NO_INFO_MARKERS):
            suggestion = self._kgc_suggestion(term)
            if suggestion:
                response = suggestion

        sources = self._extract_sources_from_context(enriched_context)
        return {
            "response": response,
            "agent": self.name,
            "agent_description": self.description,
            "context_length": len(enriched_context),
            "context": enriched_context,
            "sources": sources,
        }

    def _kgc_suggestion(self, term: str) -> str:
        """
        Usa KGCompletion para sugerir disciplinas estruturalmente similares
        quando o termo buscado não produziu contexto no vector store ou KG.
        Inspirado em APIM: score de interação entre entidades via assinatura estrutural.
        """
        if not term or not self.knowledge_graph:
            return ""
        try:
            similar = self.knowledge_graph.kgc.find_similar(term, n=3, threshold=0.08)
            if not similar:
                return ""
            nomes = [f"**{d}**" for d, _ in similar]
            return (
                f"Não encontrei informações sobre **{term}** diretamente. "
                f"Com base na estrutura do grafo de conhecimento, disciplinas "
                f"estruturalmente relacionadas são: {', '.join(nomes)}. "
                f"Você quis dizer alguma delas?"
            )
        except Exception:
            return ""

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
        seen = set()
        uniq = []
        for s in cleaned:
            if s in seen:
                continue
            seen.add(s)
            uniq.append(s)
        return uniq
