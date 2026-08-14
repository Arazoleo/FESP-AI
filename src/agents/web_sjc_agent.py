"""
Agente Web SJC - cobertura completa do site do campus São José dos Campos.

Responde perguntas sobre qualquer parte do site institucional (graduação,
secretaria, ingresso, pós-graduação, biblioteca, contatos, órgãos, etc.) a
partir de um corpus rastreado pelo `site_crawler`, recuperando as páginas mais
relevantes e respondendo ancorado, sempre citando o link da fonte.

Recuperação: similaridade por embeddings (reusa o modelo do RAG) com fallback
para sobreposição de palavras-chave. Conteúdo é EXTERNO (não validado pelo KG),
por isso a resposta sempre cita a página oficial usada.
"""

import re
import time
import unicodedata
import logging
from urllib.parse import urlparse, unquote
from typing import Dict, Any, List, Tuple, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent, fix_response_links
from ..site_crawler import load_cache, crawl_sjc, BASE

logger = logging.getLogger("fespai.web_sjc")

_TOP_K = 3
_EXCERPT = 1800
_MIN_EMBED = 0.55
_MIN_EMBED_MARGIN = 0.15
_MIN_KEYWORD = 2.0
_STOP = frozenset({
    "para", "como", "qual", "quais", "quando", "onde", "sobre", "tem", "esta",
    "estao", "mais", "uma", "que", "com", "por", "dos", "das", "isso", "essa",
    "esse", "unifesp", "campus", "sjc", "quero", "saber", "gostaria", "pode",
    "fazer", "preciso", "tenho", "fica", "ictsjc", "ict",
})


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


_ACRONYMS = frozenset({
    "bct", "bcc", "ec", "eb", "em", "bmc", "bbt", "nde", "ppc", "tcc", "uc", "ucs",
})

_ACRONYM_EXPANSION = {
    "bct": {"bacharelado", "interdisciplinar", "ciencia", "tecnologia"},
    "bcc": {"bacharelado", "ciencia", "computacao"},
    "ec": {"engenharia", "computacao"},
    "eb": {"engenharia", "biomedica"},
    "em": {"engenharia", "materiais"},
    "bmc": {"matematica", "computacional"},
    "bbt": {"biotecnologia"},
}


def _tokens(s: str) -> set:
    s = _strip_accents((s or "").lower())
    return {
        t for t in re.findall(r"[a-z0-9]+", s)
        if (len(t) > 3 or t in _ACRONYMS) and t not in _STOP
    }


def _slug_text(url: str) -> str:
    path = unquote(urlparse(url or "").path)
    path = path.split("#", 1)[0]
    return re.sub(r"[-_/]+", " ", path).strip()


def _slug_tokens(url: str) -> set:
    return _tokens(_slug_text(url))


def search_site_sections(question: str, top_k: int = 2) -> List[Dict]:
    """
    Busca por keywords nas seções do corpus do site (sem embeddings).

    Reutilizada por outros agentes (ex.: CursosAgent) para complementar
    respostas do KG com as páginas do site - as duas bases "conversando".
    """
    cache = load_cache()
    if not cache or not cache.get("pages"):
        return []
    corpus = cache["pages"]
    qt = _tokens(question)
    for a in list(qt):
        qt |= _ACRONYM_EXPANSION.get(a, set())
    scored = [
        (
            2.0 * len(qt & _tokens(p["titulo"]))
            + 1.5 * len(qt & _slug_tokens(p["url"]))
            + len(qt & _tokens(p["texto"][:1000])),
            p,
        )
        for p in corpus
    ]
    scored.sort(key=lambda x: -x[0])
    return [p for s, p in scored[:top_k] if s >= _MIN_KEYWORD]


class WebSjcAgent(BaseAgent):

    name = "web_sjc"
    description = "Busca em qualquer página do site do campus UNIFESP SJC"
    color = "#0ea5e9"

    def __init__(self, rag_instance):
        super().__init__(rag_instance)
        self._corpus: Optional[List[Dict]] = None
        self._site_db = None
        self._site_db_ts: float = 0.0
        self._corpus_ts: float = 0.0
        self._last_mode: str = "keyword"

    def retrieve(self, question: str, intent: str, term: str) -> str:
        return ""

    def get_prompt_template(self) -> str:
        return (
            "Voce e o assistente virtual da UNIFESP ICT (campus Sao Jose dos Campos), "
            "simpatico e prestativo. Responda a pergunta usando SOMENTE o material de "
            "referencia abaixo. Fale PORTUGUES BRASILEIRO.\n\n"
            "MATERIAL DE REFERENCIA:\n{context}\n\n"
            "Pergunta: {question}\n\n"
            "Regras:\n"
            "- Use apenas o conteudo acima; NAO invente dados (telefones, e-mails, prazos, nomes).\n"
            "- O bloco [FATOS VERIFICADOS NO KNOWLEDGE GRAPH], quando presente, e a fonte "
            "de verdade: se alguma pagina do site divergir dele, siga o KG e mencione "
            "brevemente que a pagina pode estar desatualizada.\n"
            "- Quando citar uma informacao de pagina do site, indique de qual pagina veio (inclua o link).\n"
            "- Se a resposta nao estiver no material acima, diga com gentileza que nao "
            "encontrou isso no site e sugira o link mais proximo ou os contatos do campus.\n"
            "- Seja conversacional e direto. NAO use emojis.\n\nResposta:"
        )

    def _find_curso_in_question(self, question: str) -> str:
        """Retorna o nome do curso do KG citado na pergunta (nome ou sigla)."""
        kg = self.knowledge_graph
        if not kg:
            return ""
        qn = f" {kg._normalize_text(question)} "
        best, best_len = "", 0
        for _, data in kg.graph.nodes(data=True):
            if data.get("tipo") not in ("curso", "matriz_curricular"):
                continue
            for chave in (data.get("nome", ""), data.get("sigla") or ""):
                cn = kg._normalize_text(chave)
                if cn and len(cn) > best_len and f" {cn} " in qn:
                    best, best_len = data.get("nome", ""), len(cn)
        return best

    def _documentos_institucionais(self, question: str, k: int = 2) -> str:
        """
        Fusão site ↔ documentos institucionais: anexa os trechos mais
        relevantes de regulamentos/manuais/PPCs do corpus, rotulados, para o
        LLM compor com as páginas do site (item 9 do backlog).
        """
        if not getattr(self, "db", None):
            return ""
        try:
            docs = self.db.similarity_search(
                question, k=k, filter={"tipo_documento": "institucional"}
            )
        except Exception:
            return ""
        trechos = [d.page_content.strip() for d in docs if d.page_content.strip()]
        if not trechos:
            return ""
        return (
            "### [DOCUMENTOS INSTITUCIONAIS - regulamentos e manuais oficiais]\n\n"
            + "\n---\n".join(trechos)
        )

    def _kg_verified_facts(self, question: str) -> str:
        """
        Fatos verificados do KG sobre entidades citadas na pergunta.

        Quando a pergunta toca as duas bases (ex.: "o que é o BCT?" tem página
        no site E matriz no KG), o contexto de geração recebe os dois blocos -
        e o prompt dá precedência ao KG em caso de divergência.
        """
        if not self.knowledge_graph or not self.graph_rag:
            return ""
        blocos: List[str] = []

        curso = self._find_curso_in_question(question)
        if curso:
            for intent in ("matriz_info", "coordenador_curso"):
                try:
                    resp = self.graph_rag.query_graph(intent, curso)
                except Exception:
                    resp = None
                if resp and "não encontrei" not in resp.lower():
                    blocos.append(resp[:700])

        try:
            disciplina = self.graph_rag._find_discipline_in_text(question)
            if disciplina and self.validator:
                facts = self.validator._build_discipline_facts(disciplina)
                if facts:
                    blocos.append(facts[:700])
        except Exception:
            pass

        if not blocos:
            return ""
        return (
            "### [FATOS VERIFICADOS NO KNOWLEDGE GRAPH]\n"
            "(fonte de verdade - em caso de conflito com as paginas, siga isto)\n\n"
            + "\n\n".join(blocos)
        )

    def _ensure_corpus(self) -> List[Dict]:
        cache = load_cache()
        if cache and cache.get("pages"):
            ts = float(cache.get("ts", 0))
            if self._corpus is None or ts > self._corpus_ts:
                self._corpus = cache["pages"]
                self._corpus_ts = ts
            return self._corpus
        if self._corpus is not None:
            return self._corpus
        try:
            self._corpus = crawl_sjc(max_pages=300)
            self._corpus_ts = time.time()
        except Exception as e:
            logger.warning("[web_sjc] crawl inicial falhou: %s", e)
            self._corpus = []
        return self._corpus

    def _ensure_site_db(self, corpus: List[Dict]):
        cache = load_cache()
        if not cache or not cache.get("pages"):
            return None
        ts = float(cache.get("ts", 0))
        if self._site_db is not None and ts == self._site_db_ts:
            return self._site_db
        emb = getattr(self.rag, "embeddings", None)
        persist = getattr(getattr(self.rag, "config", None), "PERSIST_DIR", None)
        if not emb or not persist:
            return None
        from ..site_index import ensure_site_collection
        from ..task_embeddings import embedding_signature

        sig = embedding_signature(
            getattr(self.rag.config, "EMBEDDING_MODEL", "") or ""
        )
        self._site_db = ensure_site_collection(emb, str(persist), cache, sig)
        self._site_db_ts = ts
        return self._site_db

    def _keyword_scores(self, question: str, corpus: List[Dict]) -> List[float]:
        qt = _tokens(question)
        for a in list(qt):
            qt |= _ACRONYM_EXPANSION.get(a, set())
        return [
            2.0 * len(qt & _tokens(p["titulo"]))
            + 1.5 * len(qt & _slug_tokens(p["url"]))
            + len(qt & _tokens(p["texto"][:1000]))
            for p in corpus
        ]

    def _rank(self, question: str, corpus: List[Dict]) -> List[Tuple[float, Dict]]:
        kw_scores = self._keyword_scores(question, corpus)
        db = self._ensure_site_db(corpus)
        if db is not None:
            from ..site_index import buscar_site, rrf_indices

            idxs_vec = buscar_site(db, question, k=20)
            idxs_kw = [
                i for i in sorted(range(len(corpus)), key=lambda i: -kw_scores[i])
                if kw_scores[i] >= _MIN_KEYWORD
            ][:12]
            merged = rrf_indices([idxs_vec, idxs_kw], top_n=20)
            merged = [i for i in merged if 0 <= i < len(corpus)]
            if merged:
                self._last_mode = "hybrid"
                n = len(merged)
                return [
                    ((n - pos) / n, corpus[i]) for pos, i in enumerate(merged)
                ]
        self._last_mode = "keyword"
        scored = [
            (kw_scores[i], corpus[i])
            for i in range(len(corpus))
        ]
        scored.sort(key=lambda x: -x[0])
        return scored

    def _build_context(self, paginas: List[Dict]) -> str:
        partes = []
        for p in paginas:
            partes.append(f"### {p['titulo']}\nLink: {p['url']}\n\n{p['texto'][:_EXCERPT]}")
        return "\n\n".join(partes)

    def _result(self, response: str, paginas: List[Dict] = None) -> Dict[str, Any]:
        return {
            "response": response,
            "agent": self.name,
            "agent_description": self.description,
            "context_length": 0,
            "context": "",
            "sources": [p["url"] for p in paginas] if paginas else [],
        }

    def answer(self, question: str, intent: str, term: str, history: str = "",
               student_context: str = "") -> Dict[str, Any]:
        corpus = self._ensure_corpus()
        if not corpus:
            return self._result(
                "Não consegui acessar o site do campus agora. 😕 "
                f"Você pode navegar direto em {BASE}/sjc"
            )

        ranked = self._rank(question, corpus)
        if self._last_mode == "hybrid":
            min_score = 0.0
        elif self._last_mode == "embed":
            scores_all = [s for s, _ in ranked]
            mediana = scores_all[len(scores_all) // 2] if scores_all else 0.0
            min_score = min(_MIN_EMBED, mediana + _MIN_EMBED_MARGIN)
        else:
            min_score = _MIN_KEYWORD
        top = [p for score, p in ranked[:_TOP_K] if score >= min_score][:_TOP_K]
        if not top:
            return self._result(
                "Não encontrei isso nas páginas do site do campus. "
                f"Dá uma olhada no mapa do site: {BASE}/sjc/mapa-do-site",
            )

        if not self.llm:
            linhas = ["Encontrei estas páginas do site do campus que podem ajudar:", ""]
            linhas += [f"- **[{p['titulo']}]({p['url']})**" for p in top]
            return self._result("\n".join(linhas), top)

        try:
            template = self._apply_history(self.get_prompt_template(), history)
            prompt = ChatPromptTemplate.from_template(template)
            chain = prompt | self.llm | StrOutputParser()
            contexto = self._build_context(top)
            kg_facts = self._kg_verified_facts(question)
            if kg_facts:
                contexto = kg_facts + "\n\n### [PAGINAS DO SITE]\n\n" + contexto
            docs_inst = self._documentos_institucionais(question)
            if docs_inst:
                contexto = contexto + "\n\n" + docs_inst
            if student_context:
                contexto = student_context + "\n\n" + contexto
            inputs = {"context": contexto, "question": question}
            if history:
                inputs["history"] = history
            resp = chain.invoke(inputs).strip()
            resp = fix_response_links(resp, contexto)
            if not any(p["url"] in resp for p in top):
                fontes = "\n".join(f"- [{p['titulo']}]({p['url']})" for p in top)
                resp = f"{resp}\n\n*Fontes:*\n{fontes}"
            result = self._result(resp, top)
            if kg_facts:
                result["sources"] = ["Knowledge Graph"] + result["sources"]
            return result
        except Exception:
            linhas = ["Encontrei estas páginas que podem ajudar:", ""]
            linhas += [f"- **[{p['titulo']}]({p['url']})**" for p in top]
            return self._result("\n".join(linhas), top)
