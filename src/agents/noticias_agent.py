"""
Agente de Notícias — retrieval ao vivo sobre fontes oficiais da UNIFESP.

Busca as notícias do campus São José dos Campos (campus.unifesp.br/sjc/noticias)
via `news_fetcher` e responde citando fonte, data e link.

Atenção: o conteúdo é EXTERNO e não passa pela validação simbólica do KG. Por
isso o agente sempre ancora a resposta nas notícias buscadas e cita a fonte —
nunca inventa fatos fora dos itens recuperados.
"""

import re
import unicodedata
from typing import Dict, Any, List, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent
from ..news_fetcher import fetch_news, fetch_article, NEWS_URL


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


# Pedidos genéricos de listagem → resposta determinística (sem LLM).
_LISTAGEM_KEYWORDS = (
    "ultimas noticias", "quais noticias", "quais as noticias", "liste as noticias",
    "lista de noticias", "me mostra as noticias", "mostra as noticias",
    "novidades", "o que tem de novo", "o que ha de novo", "tem de novidade",
    "noticias da unifesp", "noticias do campus", "noticias recentes",
)

_FONTE = f"*Fonte: notícias oficiais da UNIFESP SJC — {NEWS_URL}*"

# Stopwords para o ranqueamento de relevância (já sem acento).
_STOP = frozenset({
    "para", "como", "qual", "quais", "quando", "onde", "sobre", "tem", "esta",
    "estao", "mais", "uma", "que", "com", "por", "dos", "das", "isso", "essa",
    "esse", "unifesp", "campus", "noticia", "noticias", "novidade", "novidades",
    "acontecendo", "rolando", "saber", "quero", "gostaria", "pode", "fala",
})

# Score mínimo (título conta dobrado) para valer a pena abrir a matéria.
_DEEP_THRESHOLD = 2
_DEEP_MAX_ARTIGOS = 2


class NoticiasAgent(BaseAgent):

    name = "noticias"
    description = "Busca notícias e novidades oficiais da UNIFESP (campus SJC)"
    color = "#eab308"  # Amber

    def retrieve(self, question: str, intent: str, term: str) -> str:
        return ""

    def get_prompt_template(self) -> str:
        return (
            "Voce e o assistente virtual da UNIFESP ICT, simpatico e direto. "
            "Responda a pergunta do aluno usando SOMENTE as noticias oficiais "
            "listadas abaixo (campus Sao Jose dos Campos). Fale PORTUGUES BRASILEIRO.\n\n"
            "NOTICIAS RECENTES:\n{context}\n\n"
            "Pergunta: {question}\n\n"
            "Regras:\n"
            "- Use apenas as noticias acima; NAO invente fatos, datas ou eventos.\n"
            "- Cite o titulo e a data da(s) noticia(s) relevante(s) e inclua o link.\n"
            "- Se a resposta nao estiver nas noticias acima, diga com gentileza que "
            "nao encontrou isso nas noticias recentes e sugira acompanhar a pagina oficial.\n"
            "- Seja conversacional. Se a noticia trouxer detalhes (datas, local, inscricoes, "
            "programacao), aprofunde-se e explique-os; caso contrario, seja breve. "
            "No maximo 1 emoji.\n\nResposta:"
        )

    def _is_listagem(self, question: str) -> bool:
        q = _strip_accents(question.lower())
        return any(kw in q for kw in _LISTAGEM_KEYWORDS)

    def _format_list(self, itens: List[Dict]) -> str:
        linhas = ["Aqui estão as últimas notícias da UNIFESP (campus São José dos Campos):", ""]
        for it in itens:
            data = f" — *{it['data']}*" if it.get("data") else ""
            linhas.append(f"- **[{it['titulo']}]({it['url']})**{data}")
            if it.get("resumo"):
                linhas.append(f"  {it['resumo']}")
        linhas += ["", _FONTE]
        return "\n".join(linhas)

    def _build_context(self, itens: List[Dict]) -> str:
        partes = []
        for i, it in enumerate(itens, 1):
            data = f" ({it['data']})" if it.get("data") else ""
            resumo = f"\n   Resumo: {it['resumo']}" if it.get("resumo") else ""
            partes.append(f"{i}. {it['titulo']}{data}{resumo}\n   Link: {it['url']}")
        return "\n".join(partes)

    @staticmethod
    def _tokens(s: str) -> set:
        s = _strip_accents((s or "").lower())
        return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 3 and t not in _STOP}

    def _rank(self, question: str, itens: List[Dict]) -> List[Tuple[int, Dict]]:
        """Ordena as notícias por relevância à pergunta (título conta dobrado)."""
        qt = self._tokens(question)
        scored = []
        for it in itens:
            score = 2 * len(qt & self._tokens(it["titulo"])) + len(qt & self._tokens(it.get("resumo", "")))
            scored.append((score, it))
        scored.sort(key=lambda x: -x[0])
        return scored

    def _build_deep_context(self, artigos: List[Tuple[Dict, str]], outras: List[Dict]) -> str:
        """Contexto rico: corpo completo das notícias relevantes + títulos das demais."""
        partes = []
        for it, corpo in artigos:
            data = f" ({it['data']})" if it.get("data") else ""
            partes.append(
                f"### {it['titulo']}{data}\nLink: {it['url']}\n\nCONTEÚDO:\n{corpo}"
            )
        if outras:
            titulos = "; ".join(o["titulo"] for o in outras)
            partes.append(f"### Outras notícias recentes (apenas títulos)\n{titulos}")
        return "\n\n".join(partes)

    def answer(self, question: str, intent: str, term: str, history: str = "") -> Dict[str, Any]:
        itens = fetch_news(limit=8)

        if not itens:
            return self._result(
                "Não consegui acessar as notícias da UNIFESP agora. 😕 "
                f"Você pode vê-las direto na página oficial: {NEWS_URL}"
            )

        # Listagem genérica → resposta determinística (rápida, sem LLM).
        if self._is_listagem(question) or not self.llm:
            return self._result(self._format_list(itens), itens)

        # Pergunta específica → identifica a(s) notícia(s) relevante(s) e, se houver
        # match claro, ABRE a matéria para responder em profundidade.
        ranked = self._rank(question, itens)
        top_score = ranked[0][0] if ranked else 0
        if top_score >= _DEEP_THRESHOLD:
            # Corte relativo ao topo: evita abrir matérias só com token genérico em comum.
            cutoff = max(_DEEP_THRESHOLD, (top_score + 1) // 2)
            relevantes = [it for score, it in ranked if score >= cutoff][:_DEEP_MAX_ARTIGOS]
        else:
            relevantes = []

        try:
            if relevantes:
                artigos = []
                for it in relevantes:
                    corpo = fetch_article(it["url"]) or it.get("resumo", "")
                    artigos.append((it, corpo))
                outras = [it for it in itens if it not in relevantes][:5]
                context = self._build_deep_context(artigos, outras)
                fontes_extra = relevantes
            else:
                # Sem match forte: usa os resumos do feed (comportamento base).
                context = self._build_context(itens)
                fontes_extra = itens

            prompt = ChatPromptTemplate.from_template(self.get_prompt_template())
            chain = prompt | self.llm | StrOutputParser()
            resp = chain.invoke({"context": context, "question": question}).strip()
            if NEWS_URL not in resp:
                resp = f"{resp}\n\n{_FONTE}"
            return self._result(resp, fontes_extra)
        except Exception:
            # Degradação segura: cai para a listagem determinística.
            return self._result(self._format_list(itens), itens)

    def _result(self, response: str, itens: List[Dict] = None) -> Dict[str, Any]:
        return {
            "response": response,
            "agent": self.name,
            "agent_description": self.description,
            "context_length": 0,
            "context": "",
            "sources": [NEWS_URL] + ([it["url"] for it in itens] if itens else []),
        }
