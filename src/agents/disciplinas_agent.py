"""
Agente especializado em Disciplinas e Pré-requisitos.

Domínio: 209 UCs (Unidades Curriculares) do ICT/UNIFESP
- Pré-requisitos e cadeias de dependência
- Ementa, carga horária e bibliografia
- Docentes por disciplina
"""

import re
from typing import Optional
from .base_agent import BaseAgent


class DisciplinasAgent(BaseAgent):

    name = "disciplinas"
    description = "Especialista em disciplinas, pré-requisitos e ementas"
    color = "#10b981"  # Emerald

    GRAPH_INTENTS = {
        "prerequisite_chain",
        "dependents",
        "discipline_docentes",
    }

    def retrieve(self, question: str, intent: str, term: str) -> str:
        parts = []

        # 1. Consultar Knowledge Graph para intents estruturados
        if intent in self.GRAPH_INTENTS and term and self.graph_rag:
            graph_result = self._get_graph_context(intent, term)
            if graph_result:
                parts.append(graph_result)
                # Para prereqs e dependents, o grafo já tem tudo
                if intent in ("prerequisite_chain", "dependents"):
                    return "\n\n".join(parts)

        # 2. Buscar no vector store por documentos de disciplina
        raw_name = self._resolve_discipline_name(question, term)
        discipline_name = self._normalize_discipline_name(raw_name) if raw_name else None
        if discipline_name and self.db:
            docs = self._fetch_discipline_docs(discipline_name, question.lower())
            if docs:
                parts.append(self._format_docs(docs))

        # 3. Fallback: busca semântica genérica
        if not parts and self.rag.retriever:
            docs = self.rag.retriever.invoke(question)
            parts.append(self._format_docs(docs))

        # 4. As duas bases "conversam": seções do site do campus complementam
        #    perguntas abertas — mas NUNCA os intents estruturados de grafo
        #    (prereqs/dependents/docentes), para não poluir dados verificados.
        if intent not in self.GRAPH_INTENTS:
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

    def _resolve_discipline_name(self, question: str, term: str) -> Optional[str]:
        """Determina o nome da disciplina a partir da pergunta ou do termo extraído."""
        if term and term not in ("", "unknown"):
            words = set(term.lower().split())
            if not words.issubset(self._PRONOUN_WORDS):
                # Tentar expansão de sigla/código pelo KG antes de usar o termo bruto
                expanded = self._expand_via_kg(term)
                return expanded if expanded else term
        return self.rag._extract_discipline_name(question)

    def _normalize_discipline_name(self, name: str) -> str:
        """Remove pontuação e normaliza espaços para melhor match no banco (ex.: Matemática Discreta)."""
        if not name or not name.strip():
            return name
        s = re.sub(r"[\?.,!]+", "", name).strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def _fetch_discipline_docs(self, discipline: str, question_lower: str):
        """Busca documentos de disciplina no vector store."""
        try:
            if discipline.startswith("SIGLA:"):
                sigla = discipline.replace("SIGLA:", "")
                results = self.rag._search_by_sigla(sigla)
            else:
                results = self.db.get(where={"disciplina": discipline})
                if not results.get("ids"):
                    results = self.rag._fuzzy_discipline_search(discipline)

            if not results.get("ids"):
                return []

            from langchain_core.documents import Document

            docs = [
                Document(page_content=text, metadata=meta)
                for text, meta in zip(
                    results.get("documents", []), results.get("metadatas", [])
                )
            ]

            # Filtrar por seção relevante para a pergunta
            if any(w in question_lower for w in ("docente", "professor", "quem leciona")):
                filtered = [d for d in docs if d.metadata.get("secao") == "docentes"]
                if filtered:
                    return filtered[:3]
            if any(w in question_lower for w in ("pre-requisito", "prerequisito", "requisito")):
                filtered = [d for d in docs if d.metadata.get("secao") == "pre_requisitos"]
                if filtered:
                    return filtered[:3]
            if any(w in question_lower for w in ("carga", "hora")):
                filtered = [d for d in docs if d.metadata.get("secao") == "carga_horaria"]
                if filtered:
                    return filtered[:3]
            if any(w in question_lower for w in ("ementa", "conteudo", "tópico", "topico")):
                filtered = [d for d in docs if d.metadata.get("secao") == "ementa"]
                if filtered:
                    return filtered[:3]
            if any(w in question_lower for w in ("bibliografia", "livro")):
                filtered = [d for d in docs if "bibliografia" in d.metadata.get("secao", "")]
                if filtered:
                    return filtered[:4]
            # "O que é X?" / "Me fale sobre X" / "Fale mais sobre [disciplina]" → ementa + info_geral
            if any(
                w in question_lower
                for w in (
                    "que é",
                    "o que",
                    "o que sabe",
                    "o que vc sabe",
                    "fale sobre",
                    "fale mais",
                    "me fale mais",
                    "me fale sobre",
                    "descreva",
                    "explique",
                )
            ):
                ementa = [d for d in docs if d.metadata.get("secao") in ("ementa", "info_geral")]
                if ementa:
                    return ementa[:3]

            info_geral = [d for d in docs if d.metadata.get("secao") == "info_geral"]
            outros = [d for d in docs if d.metadata.get("secao") != "info_geral"][:4]
            return info_geral + outros

        except Exception as e:
            print(f"[DisciplinasAgent] Erro ao buscar disciplina: {e}")
            return []

    def get_prompt_template(self) -> str:
        return """Voce e o assistente virtual da UNIFESP ICT, especialista em DISCIPLINAS e PRE-REQUISITOS — simpatico e acolhedor, como um colega que ajuda os alunos. Fale sempre em PORTUGUES BRASILEIRO, de forma natural e conversacional.

""" + self.GOLDEN_RULE + """

CONTEXTO DA BASE DE DADOS:
{context}

Pergunta: {question}

INSTRUCOES:
1. Responda com base EXCLUSIVAMENTE no CONTEXTO acima — nenhuma palavra inventada.
2. Para pré-requisitos: apresente a cadeia completa de dependencias que aparece no contexto.
3. Para ementas/conteudo: descreva os topicos presentes no contexto, sem adicionar topicos extras.
4. Para informacoes gerais: cite somente nome, codigo, carga horaria e docentes que aparecem no contexto.
5. Se algum campo pedido nao estiver no contexto, omita-o ou diga que nao ha informacao.
6. O bloco [PAGINAS DO SITE DO CAMPUS], quando presente, e complemento: ao usar
   informacao dele, SEMPRE cite o link. Se divergir dos dados verificados da
   base, prefira os dados verificados e mencione a divergencia.

TOM: caloroso e direto, como num bate-papo. Pode abrir com uma frase amigavel e fechar se colocando a disposicao; no maximo 1 emoji. A precisao dos fatos vem sempre em primeiro lugar.

Resposta:"""
