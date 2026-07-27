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

        # 4. As duas bases "conversam": procedimentos práticos do site do
        #    campus complementam as normas dos regimentos.
        site_ctx = self._site_supplement(question)
        if site_ctx:
            parts.append(site_ctx)

        return "\n\n".join(parts) if parts else ""

    def _site_supplement(self, question: str) -> str:
        """Top seções do site do campus relevantes à pergunta, com link."""
        try:
            from .web_sjc_agent import search_site_sections
            secoes = search_site_sections(question, top_k=2)
        except Exception:
            return ""
        if not secoes:
            return ""
        partes = ["[PAGINAS DO SITE DO CAMPUS — complemento; cite o link ao usar]"]
        for p in secoes:
            partes.append(f"[{p['titulo']}]\nLink: {p['url']}\n{p['texto'][:1200]}")
        return "\n\n".join(partes)

    def get_prompt_template(self) -> str:
        return """Voce e o assistente virtual da UNIFESP ICT, especialista em REGIMENTOS e NORMAS INSTITUCIONAIS — atencioso e claro, ajudando os alunos a entenderem as regras sem juridiques. Fale sempre em PORTUGUES BRASILEIRO, de forma natural e conversacional.

""" + self.GOLDEN_RULE + """

CONTEXTO DA BASE DE DADOS:
{context}

Pergunta: {question}

INSTRUCOES:
1. Use SOMENTE as informacoes presentes no CONTEXTO acima.
2. Para artigos do regimento: cite o número do artigo e a seção.
3. Para FAQs: apresente pergunta e resposta de forma clara.
4. Para normas: seja preciso e cite a fonte (documento).
5. Para procedimentos: liste os passos em ordem.
6. O bloco [PAGINAS DO SITE DO CAMPUS], quando presente, e complemento
   (procedimentos praticos, formularios, contatos): ao usar informacao dele,
   SEMPRE cite o link. Se divergir das normas e regimentos verificados,
   prefira os dados verificados e mencione a divergencia.

REGRA ABSOLUTA: Se a informacao pedida NAO estiver no CONTEXTO acima, diga com gentileza que nao
tem esse dado na base da UNIFESP ICT.
NAO invente, suponha ou extrapole NENHUM dado (artigo, prazo, procedimento, etc.).

TOM: acolhedor e direto, como num bate-papo. Pode abrir com uma frase amigavel e fechar se colocando a disposicao; NAO use emojis. Explique a regra de forma simples, mas mantenha a precisao (artigos, prazos e fontes exatos).

Resposta:"""
