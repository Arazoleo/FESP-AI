"""
Agente especializado em Docentes do ICT/UNIFESP.

Domínio: corpo_docente_ict.md + Knowledge Graph
- Informações de contato (email, sala)
- Áreas de pesquisa e especialização
- Disciplinas lecionadas por docente
- Docentes por área de conhecimento
"""

import re
from .base_agent import BaseAgent


class DocentesAgent(BaseAgent):

    name = "docentes"
    description = "Especialista em docentes, áreas de pesquisa e contatos"
    color = "#8b5cf6"  # Violet

    GRAPH_INTENTS = {
        "docente_info",
        "docente_areas",
        "docente_disciplines",
        "discipline_docentes",
        "docentes_by_area",
        "docente_leciona_disciplina",
    }

    def _clean_discipline_term(self, term: str) -> str:
        """
        Remove ruído do term extraído pelo classificador para lookups de disciplina.

        O classificador às vezes retorna termos como "dão cálculo numérico?" quando
        a pergunta é "Quais docentes dão Cálculo Numérico?". Este método limpa isso.
        """
        import re
        # Remover pontuação
        cleaned = re.sub(r'[\?.,!]+', '', term).strip()
        # Remover palavras verbais e de pergunta que contaminam o term
        noise = r'\b(?:d[aã]o|leciona[m]?|ensina[m]?|ministra[m]?|docentes?|professores?)\b'
        cleaned = re.sub(noise, '', cleaned, flags=re.IGNORECASE).strip()
        # Normalizar espaços
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _detect_discipline_docentes(self, question: str) -> str:
        """
        Extrai o nome da disciplina de perguntas 'quais professores dão X?'.
        Fallback para quando o intent chegou classificado incorretamente.
        """
        patterns = [
            r'(?:professore?s?|docentes?)\s+(?:d[aã]o|que\s+(?:d[aã]o|leciona[m]?|ensina[m]?|ministra[m]?)|de|da|do)\s+(.+?)(?:\?|$)',
            r'd[aã]o\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
            r'(?:quem\s+)?(?:leciona[m]?|ensina[m]?|ministra[m]?)\s+(.+?)(?:\?|$)',
        ]
        q_lower = question.lower().strip()
        for pattern in patterns:
            m = re.search(pattern, q_lower, re.IGNORECASE)
            if m:
                t = m.group(1).strip()
                t = re.sub(r'[\?.,!]+$', '', t).strip()
                if len(t) > 3:
                    return t
        return ""

    def retrieve(self, question: str, intent: str, term: str) -> str:
        parts = []

        # 1. Knowledge Graph é a fonte primária para docentes
        if intent in self.GRAPH_INTENTS and self.graph_rag:
            # Para discipline_docentes, term é disciplina → limpar ruído antes do lookup
            # Para outros, term é docente → sanitizar (remover lixo do extrator)
            if intent == "discipline_docentes":
                cleaned = self._clean_discipline_term(term)
                # Expansão de sigla/código (ex.: "IHC" → "Interação Humano-Computador")
                lookup_term = self._expand_via_kg(cleaned) or cleaned
            else:
                # Sanitizar: extrator pode capturar "Didier Vega, como faço?"
                lookup_term = self._resolve_docente_name(term, question)

            if lookup_term:
                graph_result = self._get_graph_context(intent, lookup_term)
                if graph_result:
                    parts.append(graph_result)
                    # Para intents de disciplinas e listagens, o grafo tem tudo → retornar direto
                    # docente_info NÃO retorna cedo: queremos complementar com vector store
                    if intent in (
                        "docente_disciplines",
                        "docentes_by_area",
                        "docente_leciona_disciplina",
                    ):
                        return "\n\n".join(parts)

        # 1b. Fallback: intent classificado errado mas pergunta é "quais professores dão X?"
        #     Acontece quando o classificador semântico retorna intent errado (ex: ementa_disciplina)
        #     mas o roteador ainda enviou a pergunta para o Agente Docentes.
        if intent not in self.GRAPH_INTENTS and not parts and self.graph_rag:
            disc_from_q = self._detect_discipline_docentes(question)
            if disc_from_q:
                graph_result = self._get_graph_context("discipline_docentes", disc_from_q)
                if graph_result and "Não encontrei" not in graph_result:
                    parts.append(graph_result)
                    return "\n\n".join(parts)

        # 2. Para "quem leciona X?" o term é o nome da DISCIPLINA
        #    → buscar seção "docentes" do documento da disciplina no vector store
        if intent == "discipline_docentes" and self.db:
            cleaned = self._clean_discipline_term(term)
            disciplina_docs = self._fetch_discipline_docentes_section(
                self._expand_via_kg(cleaned) or cleaned
            )
            if disciplina_docs:
                parts.append(self._format_docs(disciplina_docs))
                return "\n\n".join(parts)

        # 3. Para "quais disciplinas X leciona?" → busca reversa em docs de disciplina
        if intent == "docente_disciplines" and not parts and self.db:
            docente_name = self._resolve_docente_name(term, question)
            if docente_name:
                docs = self._fetch_disciplines_by_docente(docente_name)
                if docs:
                    parts.append(self._format_docs(docs))

        # 3b. Fallback: intent desconhecido mas pergunta é "quais disciplinas/matérias X leciona?" ou "X dá aula de quê?"
        if not parts and self.db:
            docente_name = self._docente_disciplines_fallback(question, term)
            if docente_name:
                docs = self._fetch_disciplines_by_docente(docente_name)
                if docs:
                    parts.append(self._format_docs(docs))

        # 4. Para intents de informação sobre docente → buscar docs no vector store
        #    (complementa o KG que só tem email/sala/áreas mas não disciplinas lecionadas)
        if intent in ("docente_info", "docente_areas") and self.db:
            try:
                docente_name = self._resolve_docente_name(term, question)
                if docente_name:
                    docs = self._fetch_docente_docs(docente_name)
                    if docs:
                        parts.append(self._format_docs(docs))
            except Exception as e:
                print(f"[DocentesAgent] Erro ao buscar docente: {e}")

        # 4. Fallback: busca semântica no vector store
        if not parts and self.rag.retriever:
            docs = self.rag.retriever.invoke(question)
            parts.append(self._format_docs(docs))

        return "\n\n".join(parts) if parts else ""

    def _resolve_docente_name(self, term: str, question: str) -> str:
        """
        Determina o nome limpo do docente a partir do termo extraído e/ou da pergunta.

        O extrator de termos pode retornar lixo como "Didier Vega, como faço?".
        Este método:
        1. Extrai o nome próprio da pergunta (padrões mais precisos)
        2. Usa o term original se não encontrar nada melhor
        3. Remove fragmentos de pergunta que "vazaram" para o term
        """
        import re

        # Tentar extrair nome da pergunta diretamente (mais confiável)
        extracted = self._extract_docente_name(question)
        if extracted:
            # Canonicalizar via KG: "Didier" → "Didier Vega-Oliveros"
            return self._expand_via_kg(extracted, "docente") or extracted

        # Limpar o term: manter apenas sequência de palavras capitalizadas
        if term:
            # Parar na primeira vírgula, ponto de interrogação ou palavra-chave de pergunta
            clean = re.split(r'[,?.]|(?:\bcomo\b|\bqual\b|\bonde\b|\bquem\b)', term, flags=re.IGNORECASE)[0]
            clean = clean.strip()
            if len(clean) >= 3:
                return self._expand_via_kg(clean, "docente") or clean

        return term or ""

    def _extract_docente_name(self, question: str) -> str:
        """Extrai nome de docente da pergunta usando padrões precisos."""
        import re
        patterns = [
            # "com o Didier Vega" / "com a Thaciana" — mais direto que "professor X"
            r"com\s+(?:o|a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)",
            # "do Álvaro" / "da Maria" quando precedido de contato/email/sala
            r"(?:contato|email|sala)\s+(?:de|do|da)\s+(?:professor(?:a)?\s+)?([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)",
            # Nome próprio no início da frase seguido de vírgula ("Thaciana Malaspina, tem...")
            r"^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)\s*[,\?]",
            # "professor Didier Vega" / "professora Maria"
            r"professor(?:a)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)",
            # "docente Álvaro"
            r"docente\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)",
            # "o Álvaro leciona / pesquisa"
            r"(?:o|a)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)\s+(?:leciona|ensina|pesquisa)",
        ]
        for pattern in patterns:
            match = re.search(pattern, question, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        return ""

    def _docente_disciplines_fallback(self, question: str, term: str) -> str:
        """
        Se a pergunta for "quais disciplinas/matérias X leciona?" ou "X dá aula de quê?"
        mas o intent não foi docente_disciplines (ex.: roteamento por embedding sem graph),
        extrai o nome do docente para usar em _fetch_disciplines_by_docente.
        """
        q = question.strip()
        q_lower = q.lower()
        # Padrões que indicam pergunta por disciplinas lecionadas por alguém
        if not any(
            x in q_lower
            for x in (
                "quais disciplinas",
                "quais matérias",
                "disciplinas que",
                "matérias que",
                "dá aula de quê",
                "da aula de que",
                "leciona o quê",
                "leciona o que",
            )
        ):
            return ""
        patterns = [
            # "quais disciplinas Sanderson leciona" / "quais matérias o João dá"
            r"(?:quais?\s+)?(?:disciplinas?|mat[eé]rias?)\s+(?:que\s+)?(?:o\s+|a\s+)?(.+?)\s+(?:leciona|ensina|d[aá])\b",
            # "o Sanderson dá aula de quê?" / "a Maria leciona o quê?"
            r"(?:o\s+|a\s+)?([A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*)\s+(?:d[aá]\s+aula\s+de\s+qu[eê]|leciona\s+o\s+qu[eê])",
        ]
        for pattern in patterns:
            match = re.search(pattern, q_lower, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r"[\?.,!]+$", "", name).strip()
                if len(name) >= 2 and name.lower() not in ("que", "qual", "quais", "o", "a"):
                    return self._resolve_docente_name(name, question)
        if term and len(term) >= 2:
            return self._resolve_docente_name(term, question)
        return ""

    def _fetch_discipline_docentes_section(self, discipline_name: str):
        """
        Para "quem leciona X?": busca a seção 'docentes' do documento da disciplina.
        O term aqui é o nome da disciplina, não do docente.
        """
        if not discipline_name or not self.db:
            return []
        try:
            # Buscar docs da disciplina usando o mesmo método do DisciplinasAgent
            if discipline_name.startswith("SIGLA:"):
                sigla = discipline_name.replace("SIGLA:", "")
                results = self.rag._search_by_sigla(sigla)
            else:
                results = self.db.get(where={"disciplina": discipline_name})
                if not results.get("ids"):
                    results = self.rag._fuzzy_discipline_search(discipline_name)

            if not results.get("ids"):
                return []

            from langchain_core.documents import Document

            all_docs = [
                Document(page_content=text, metadata=meta)
                for text, meta in zip(
                    results.get("documents", []), results.get("metadatas", [])
                )
            ]

            # Priorizar seção "docentes" dentro dos docs da disciplina
            docentes_section = [
                d for d in all_docs if d.metadata.get("secao") == "docentes"
            ]
            if docentes_section:
                return docentes_section[:3]

            # Fallback: info_geral geralmente menciona docentes
            info_geral = [
                d for d in all_docs if d.metadata.get("secao") == "info_geral"
            ]
            return info_geral[:2] if info_geral else all_docs[:2]

        except Exception as e:
            print(f"[DocentesAgent] Erro ao buscar seção docentes da disciplina: {e}")
            return []

    def _fetch_disciplines_by_docente(self, docente_name: str):
        """
        Para "quais disciplinas X leciona?": busca reversa nos documentos de
        disciplinas — encontra quais têm o docente listado na seção 'docentes'.
        """
        if not docente_name or not self.db:
            return []
        try:
            # Buscar docs de disciplina com seção "docentes"
            results = self.db.get(where={"secao": "docentes"})
            if not results.get("ids"):
                # Fallback: buscar docs de disciplina gerais
                results = self.db.get(where={"tipo_documento": "disciplina"})
            if not results.get("ids"):
                return []

            from langchain_core.documents import Document

            name_lower = docente_name.lower()
            # Partes do nome para match parcial (sobrenome é mais único)
            name_parts = [p.lower() for p in docente_name.split() if len(p) > 3]

            matching_docs = []
            seen_disciplines = set()

            for text, meta in zip(
                results.get("documents", []), results.get("metadatas", [])
            ):
                text_lower = text.lower()
                disciplina = meta.get("disciplina", "")

                # Evitar duplicatas da mesma disciplina
                if disciplina in seen_disciplines:
                    continue

                matched = False
                if name_lower in text_lower:
                    matched = True
                elif name_parts:
                    # Match pelo sobrenome (mais específico que o primeiro nome)
                    last_name = name_parts[-1]
                    if len(last_name) > 4 and last_name in text_lower:
                        matched = True

                if matched:
                    matching_docs.append(Document(page_content=text, metadata=meta))
                    if disciplina:
                        seen_disciplines.add(disciplina)

            return matching_docs[:10]

        except Exception as e:
            print(f"[DocentesAgent] Erro na busca reversa por disciplinas: {e}")
            return []

    def _fetch_docente_docs(self, docente_name: str):
        """Busca documentos de docente no vector store."""
        try:
            results = self.db.get(where={"tipo_documento": "docente"})
            if not results.get("ids"):
                return []

            from langchain_core.documents import Document

            name_lower = docente_name.lower()
            name_parts = docente_name.strip().split()
            matching_docs = []
            for text, meta in zip(
                results.get("documents", []), results.get("metadatas", [])
            ):
                if name_lower in text.lower() or name_lower in str(meta).lower():
                    matching_docs.append(Document(page_content=text, metadata=meta))

            # Se o termo é um único nome e há vários matches, priorizar o doc onde
            # esse nome é o PRIMEIRO nome (evita "Rodrigo" pegar Martin Rodrigo em vez de Rodrigo Colnago)
            if len(name_parts) == 1 and len(matching_docs) > 1:
                def first_name_priority(doc):
                    text = doc.page_content
                    for line in text.split("\n"):
                        if name_lower not in line.lower():
                            continue
                        # Remover prefixos "### Prof. Dr." e pegar início do nome
                        rest = re.sub(
                            r"^#*\s*(?:Prof\.?\s*(?:Dr\.?|Dra\.?|Ms\.?)?\s*)*",
                            "",
                            line,
                            flags=re.IGNORECASE,
                        ).strip()
                        if rest.lower().startswith(name_lower + " ") or rest.lower() == name_lower:
                            return 0
                    return 1

                matching_docs.sort(key=first_name_priority)

            return matching_docs[:5]
        except Exception:
            return []

    def get_prompt_template(self) -> str:
        return """Voce e o assistente virtual da UNIFESP ICT, especialista no CORPO DOCENTE — simpatico e prestativo, como um colega que conhece bem os professores do instituto. Fale sempre em PORTUGUES BRASILEIRO, de forma natural e conversacional.

""" + self.GOLDEN_RULE + """

CONTEXTO DA BASE DE DADOS:
{context}

Pergunta: {question}

INSTRUCOES:
1. Use SOMENTE as informacoes presentes no CONTEXTO acima.
2. Para informacoes de contato: apresente email e sala exatamente como aparecem no contexto.
3. Para areas de pesquisa: liste todas as areas do docente presentes no contexto.
4. Para disciplinas lecionadas: o contexto mostra documentos de cada disciplina com seus docentes.
   Liste APENAS as disciplinas onde o nome do professor aparece explicitamente na secao de docentes.
5. Para "fale sobre o professor X" ou "quem é X": combine todas as informações disponíveis no
   contexto: email, sala, áreas de pesquisa e disciplinas lecionadas.

REGRA ABSOLUTA: Se a informacao pedida NAO estiver no CONTEXTO acima, diga com gentileza que nao
tem esse dado na base da UNIFESP ICT.
NAO invente, suponha ou extrapole NENHUM dado (email, sala, area de pesquisa, disciplina, etc.).
NUNCA fabrique um endereco de email ou numero de sala.

TOM: caloroso e direto, como num bate-papo. Pode abrir com uma frase amigavel e fechar se colocando a disposicao; no maximo 1 emoji. A precisao dos fatos vem sempre em primeiro lugar.

Resposta:"""
