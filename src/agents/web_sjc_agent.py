"""
Agente Web SJC — cobertura completa do site do campus São José dos Campos.

Responde perguntas sobre qualquer parte do site institucional (graduação,
secretaria, ingresso, pós-graduação, biblioteca, contatos, órgãos, etc.) a
partir de um corpus rastreado pelo `site_crawler`, recuperando as páginas mais
relevantes e respondendo ancorado, sempre citando o link da fonte.

Recuperação: similaridade por embeddings (reusa o modelo do RAG) com fallback
para sobreposição de palavras-chave. Conteúdo é EXTERNO (não validado pelo KG),
por isso a resposta sempre cita a página oficial usada.
"""

import re
import math
import time
import unicodedata
import logging
from typing import Dict, Any, List, Tuple, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent
from ..site_crawler import load_cache, crawl_sjc, BASE

logger = logging.getLogger("fespai.web_sjc")

_TOP_K = 3
_EXCERPT = 1800  # chars por página no contexto do LLM
# Limiares mínimos de relevância (evita responder a partir de página irrelevante).
_MIN_EMBED = 0.55   # teto absoluto (calibrado p/ mxbai; ver margem abaixo)
# Cada modelo de embedding tem sua escala de cossenos (mxbai: relevante ~0.6+;
# embeddinggemma: relevante ~0.49, irrelevante ~0.27). Limiar absoluto quebra ao
# trocar de modelo — o critério robusto é relativo: o top precisa se destacar da
# MEDIANA do corpus para aquela query por esta margem.
_MIN_EMBED_MARGIN = 0.15
_MIN_KEYWORD = 2.0  # sobreposição ponderada de palavras-chave
_STOP = frozenset({
    "para", "como", "qual", "quais", "quando", "onde", "sobre", "tem", "esta",
    "estao", "mais", "uma", "que", "com", "por", "dos", "das", "isso", "essa",
    "esse", "unifesp", "campus", "sjc", "quero", "saber", "gostaria", "pode",
    "fazer", "preciso", "tenho", "fica", "ictsjc", "ict",
})


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Siglas curtas que importam para o ranking (o filtro de tamanho as descartaria)
_ACRONYMS = frozenset({
    "bct", "bcc", "ec", "eb", "em", "bmc", "bbt", "nde", "ppc", "tcc", "uc", "ucs",
})

# Expansão de sigla de curso → tokens do nome completo. Aplicada só ao QUERY no
# fallback por keywords: os títulos das seções usam o nome por extenso, então
# "ingresso no BCT" precisa casar com "Bacharelado Interdisciplinar em..."
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


def _cosine(a: List[float], b: List[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return num / (na * nb) if na and nb else 0.0


def search_site_sections(question: str, top_k: int = 2) -> List[Dict]:
    """
    Busca por keywords nas seções do corpus do site (sem embeddings).

    Reutilizada por outros agentes (ex.: CursosAgent) para complementar
    respostas do KG com as páginas do site — as duas bases "conversando".
    """
    cache = load_cache()
    if not cache or not cache.get("pages"):
        return []
    corpus = cache["pages"]
    qt = _tokens(question)
    for a in list(qt):
        qt |= _ACRONYM_EXPANSION.get(a, set())
    scored = [
        (2.0 * len(qt & _tokens(p["titulo"])) + len(qt & _tokens(p["texto"][:1000])), p)
        for p in corpus
    ]
    scored.sort(key=lambda x: -x[0])
    return [p for s, p in scored[:top_k] if s >= _MIN_KEYWORD]


class WebSjcAgent(BaseAgent):

    name = "web_sjc"
    description = "Busca em qualquer página do site do campus UNIFESP SJC"
    color = "#0ea5e9"  # Sky

    def __init__(self, rag_instance):
        super().__init__(rag_instance)
        self._corpus: Optional[List[Dict]] = None
        self._page_vecs: Optional[List[List[float]]] = None
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

    # ── Fusão com o Knowledge Graph (as duas bases "conversam") ───────────────
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

    def _kg_verified_facts(self, question: str) -> str:
        """
        Fatos verificados do KG sobre entidades citadas na pergunta.

        Quando a pergunta toca as duas bases (ex.: "o que é o BCT?" tem página
        no site E matriz no KG), o contexto de geração recebe os dois blocos —
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

        # Disciplina citada (ex.: pergunta de site que menciona uma UC)
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
            "(fonte de verdade — em caso de conflito com as paginas, siga isto)\n\n"
            + "\n\n".join(blocos)
        )

    # ── Corpus & vetores ──────────────────────────────────────────────────────
    def _ensure_corpus(self) -> List[Dict]:
        cache = load_cache()
        # Recarrega se houver um cache mais novo (ex.: após POST /crawl-sjc).
        if cache and cache.get("pages"):
            ts = float(cache.get("ts", 0))
            if self._corpus is None or ts > self._corpus_ts:
                self._corpus = cache["pages"]
                self._corpus_ts = ts
                self._page_vecs = None  # invalida vetores para reindexar
            return self._corpus
        if self._corpus is not None:
            return self._corpus
        # Primeiro uso sem cache: rastreia (capado) e guarda.
        try:
            self._corpus = crawl_sjc(max_pages=300)
            self._corpus_ts = time.time()
        except Exception as e:
            logger.warning("[web_sjc] crawl inicial falhou: %s", e)
            self._corpus = []
        return self._corpus

    def _ensure_vectors(self, corpus: List[Dict]) -> Optional[List[List[float]]]:
        if self._page_vecs is not None:
            return self._page_vecs
        emb = getattr(self.rag, "embeddings", None)
        if not emb or not corpus:
            return None
        try:
            textos = [f"{p['titulo']}. {p['texto'][:600]}" for p in corpus]
            self._page_vecs = emb.embed_documents(textos)
        except Exception as e:
            logger.warning("[web_sjc] embeddings indisponíveis, usando keyword: %s", e)
            self._page_vecs = None
        return self._page_vecs

    def _rank(self, question: str, corpus: List[Dict]) -> List[Tuple[float, Dict]]:
        vecs = self._ensure_vectors(corpus)
        if vecs:
            try:
                qv = self.rag.embeddings.embed_query(question)
                scored = [(_cosine(qv, vecs[i]), corpus[i]) for i in range(len(corpus))]
                scored.sort(key=lambda x: -x[0])
                self._last_mode = "embed"
                return scored
            except Exception:
                pass
        # Fallback por palavras-chave (título conta dobrado).
        self._last_mode = "keyword"
        qt = _tokens(question)
        for a in list(qt):
            qt |= _ACRONYM_EXPANSION.get(a, set())
        scored = [
            (2.0 * len(qt & _tokens(p["titulo"])) + len(qt & _tokens(p["texto"][:1000])), p)
            for p in corpus
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

    # ── Resposta ──────────────────────────────────────────────────────────────
    def answer(self, question: str, intent: str, term: str, history: str = "") -> Dict[str, Any]:
        corpus = self._ensure_corpus()
        if not corpus:
            return self._result(
                "Não consegui acessar o site do campus agora. 😕 "
                f"Você pode navegar direto em {BASE}/sjc"
            )

        ranked = self._rank(question, corpus)
        if self._last_mode == "embed":
            scores_all = [s for s, _ in ranked]
            mediana = scores_all[len(scores_all) // 2] if scores_all else 0.0
            # Relativo à distribuição do modelo em uso (agnóstico a modelo)
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
            # Sem LLM: devolve os links mais relevantes.
            linhas = ["Encontrei estas páginas do site do campus que podem ajudar:", ""]
            linhas += [f"- **[{p['titulo']}]({p['url']})**" for p in top]
            return self._result("\n".join(linhas), top)

        try:
            template = self._apply_history(self.get_prompt_template(), history)
            prompt = ChatPromptTemplate.from_template(template)
            chain = prompt | self.llm | StrOutputParser()
            contexto = self._build_context(top)
            # Fusão: fatos verificados do KG entram antes das páginas do site
            kg_facts = self._kg_verified_facts(question)
            if kg_facts:
                contexto = kg_facts + "\n\n### [PAGINAS DO SITE]\n\n" + contexto
            inputs = {"context": contexto, "question": question}
            if history:
                inputs["history"] = history
            resp = chain.invoke(inputs).strip()
            # Garante rastro da(s) fonte(s).
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
