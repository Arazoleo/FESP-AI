"""
Agente especializado em Regimentos e Normas Institucionais.

Domínio: regimentos, normas, FAQs, regulamentos da UNIFESP ICT
- Regimento geral do ICT
- Normas de atividades complementares
- FAQs institucionais
- Artigos e resoluções
"""

from .base_agent import BaseAgent


class RegimentosAgent(BaseAgent):

    name = "regimentos"
    description = "Especialista em normas, regimentos e regulamentos institucionais"
    color = "#ef4444"  # Red

    GRAPH_INTENTS = {
        "artigos_sobre",
        "faqs",
    }

    def retrieve(self, question: str, intent: str, term: str) -> str:
        parts = []
        question_lower = question.lower()

        # 1. Knowledge Graph para artigos e FAQs estruturados
        if intent in self.GRAPH_INTENTS and term and self.graph_rag:
            graph_result = self._get_graph_context(intent, term)
            if graph_result:
                parts.append(graph_result)

        # 2. RAG vector store para documentos institucionais (fonte primária)
        if self.db:
            docs = self.rag._retrieve_regimento_docs(question_lower)
            if docs:
                parts.append(self._format_docs(docs))

        # 3. Fallback: busca semântica
        if not parts and self.rag.retriever:
            docs = self.rag.retriever.invoke(question)
            parts.append(self._format_docs(docs))

        return "\n\n".join(parts) if parts else ""

    def get_prompt_template(self) -> str:
        return """Voce e o Assistente UNIFESP ICT especializado em REGIMENTOS e NORMAS INSTITUCIONAIS.
Responda APENAS em PORTUGUES BRASILEIRO.

CONTEXTO DA BASE DE DADOS:
{context}

Pergunta: {question}

INSTRUCOES:
1. Use SOMENTE as informacoes presentes no CONTEXTO acima.
2. Para artigos do regimento: cite o número do artigo e a seção.
3. Para FAQs: apresente pergunta e resposta de forma clara.
4. Para normas: seja preciso e cite a fonte (documento).
5. Para procedimentos: liste os passos em ordem.

REGRA ABSOLUTA: Se a informacao pedida NAO estiver no CONTEXTO acima, responda:
"Nao tenho essa informacao na base de dados da UNIFESP ICT."
NAO invente, suponha ou extrapole NENHUM dado (artigo, prazo, procedimento, etc.).

Resposta (baseada SOMENTE no contexto acima):"""
