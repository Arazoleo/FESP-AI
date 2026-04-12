"""
Agente especializado em Cursos e Matrizes Curriculares.

Domínio: 7 matrizes curriculares da UNIFESP ICT
- EC, BCC, EM, EB, BT, MC + Cursos Sequenciais
- Disciplinas por termo
- Eletivas por grupo
- Coordenação de curso
"""

from .base_agent import BaseAgent


class CursosAgent(BaseAgent):

    name = "cursos"
    description = "Especialista em matrizes curriculares e estrutura dos cursos"
    color = "#f59e0b"  # Amber

    GRAPH_INTENTS = {
        "disciplinas_termo",
        "todos_termos_curso",
        "matriz_info",
        "eletivas_curso",
        "listar_cursos",
        "coordenador_curso",
    }

    # Keywords que indicam necessidade de RAG (docs têm mais info que o grafo)
    RAG_SUPPLEMENT_KEYWORDS = [
        "sequencial", "sequenciais", "certificado",
        "carga horária total", "carga horaria total",
        "coordenador", "coordenadora", "vice-coordenador",
        "informações sobre", "detalhes do curso",
        "engenharia de computação", "engenharia de computacao",
        "ciência da computação", "ciencia da computacao",
        "engenharia de materiais", "engenharia biomedica", "engenharia biomédica",
        "biotecnologia", "matemática computacional", "matematica computacional",
        "fundamentos de ciência", "fundamentos de ciencia",
        "métodos estatísticos", "metodos estatisticos",
        "economia e mercados", "química aplicada", "quimica aplicada",
        "desenvolvimento de games", "jogos digitais",
    ]

    def retrieve(self, question: str, intent: str, term: str) -> str:
        parts = []
        question_lower = question.lower()

        # 1. Knowledge Graph para estrutura curricular
        if intent in self.GRAPH_INTENTS and self.graph_rag:
            graph_result = self._get_graph_context(intent, term)
            if graph_result:
                parts.append(graph_result)
                # Para listagem de cursos e info de matriz, o grafo é suficiente
                # para eletivas e termos, o RAG pode complementar
                if intent in ("listar_cursos",) and not any(
                    kw in question_lower for kw in self.RAG_SUPPLEMENT_KEYWORDS
                ):
                    return "\n\n".join(parts)

        # 2. RAG vector store para detalhes de matrizes e cursos sequenciais
        if self.db:
            rag_docs = self.rag._retrieve_regimento_docs(question_lower)
            if rag_docs:
                parts.append(self._format_docs(rag_docs))

        # 3. Fallback: busca semântica
        if not parts and self.rag.retriever:
            docs = self.rag.retriever.invoke(question)
            parts.append(self._format_docs(docs))

        return "\n\n".join(parts) if parts else ""

    def get_prompt_template(self) -> str:
        return """Voce e o Assistente UNIFESP ICT especializado em CURSOS e MATRIZES CURRICULARES.
Responda APENAS em PORTUGUES BRASILEIRO.

CONTEXTO DA BASE DE DADOS:
{context}

Pergunta: {question}

INSTRUCOES:
1. Use SOMENTE as informacoes presentes no CONTEXTO acima.
2. Para matrizes curriculares: apresente disciplinas organizadas por termo.
3. Para eletivas: separe por grupo (Grupo 1, 2, 3, Extensionistas).
4. Para coordenação: apresente coordenador e vice-coordenador.
5. Para cursos sequenciais: liste as disciplinas do curso.
6. Cite o número de créditos e carga horária quando disponíveis.

REGRA ABSOLUTA: Se a informacao pedida NAO estiver no CONTEXTO acima, responda:
"Nao tenho essa informacao na base de dados da UNIFESP ICT."
NAO invente, suponha ou extrapole NENHUM dado (nome de curso, código, carga horária, etc.).

Resposta (baseada SOMENTE no contexto acima):"""
