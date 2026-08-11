"""
Atividades Complementares (AC) - detalhamento por eixo com resposta simbólica.

Implementa a melhoria derivada do ciclo 2 de usabilidade: respostas sobre
atividades complementares terminam com uma OFERTA de follow-up ("quer o
detalhamento por eixo?") e, quando o aluno aceita (ou pede direto), o
detalhamento vem DIRETO do regulamento estruturado
(`jsons_regimentos/regulamento_atividades_complementares_bct_2023.json`) -
caminho simbólico, sem LLM, zero alucinação por construção.

Três peças, consumidas em pontos distintos do pipeline:
  - `is_breakdown_request`  → router (atalho simbólico, antes dos agentes)
  - `maybe_append_offer`    → query_with_metadata (pós-resposta)
  - `is_affirmative_reply` + `BREAKDOWN_CANONICAL_QUESTION`
                            → ContextResolver (aceite curto vira pedido canônico)
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

_REGULAMENTO_PATH = (
    Path(__file__).resolve().parent.parent
    / "jsons_regimentos"
    / "regulamento_atividades_complementares_bct_2023.json"
)

OFFER_MARKER = "detalhamento do que conta em cada eixo"

FOLLOWUP_OFFER = (
    "Se quiser, posso trazer o detalhamento do que conta em cada eixo das "
    "atividades complementares (com exemplos de atividades aceitas e limites "
    "de horas) - é só pedir."
)

BREAKDOWN_CANONICAL_QUESTION = (
    "Detalhe o que conta em cada eixo das atividades complementares"
)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _norm(text: str) -> str:
    """minúsculas, sem acentos, espaços colapsados."""
    return re.sub(r"\s+", " ", _strip_accents((text or "").lower())).strip()


_AC_RE = re.compile(r"\batividades?\s+complementar(?:es)?\b|\bacs?\b|\baces?\b")


def is_ac_question(question: str) -> bool:
    """True se a pergunta menciona atividades complementares."""
    return bool(_AC_RE.search(_norm(question)))


_DETAIL_CUES = [
    r"\bcada\s+(?:eixo|categoria)\b",
    r"\bpor\s+(?:eixo|categoria)\b",
    r"\b(?:quais|que)\s+(?:sao\s+)?(?:os\s+)?eixos\b",
    r"\bo\s+que\s+(?:conta|vale|pode\s+ser\s+aceito|e\s+aceito)\b",
    r"\bquais\s+atividades\s+(?:contam|valem|sao\s+aceitas|posso)\b",
    r"\btipos\s+de\s+atividades?\b",
    r"\bdetalh\w+\b",
    r"\bexemplos?\s+de\s+atividades?\b",
    r"\b(?:conta(?:m)?|vale(?:m)?|usar|validar|aproveitar)\b[^?.!]*\bcomo\s+atividades?\s+complementar(?:es)?\b",
]
_DETAIL_CUES_RES = [re.compile(p) for p in _DETAIL_CUES]

_AC_CONTEXT_RE = re.compile(r"\batividades?\s+complementar(?:es)?\b|\beixos?\b")


_NOT_BREAKDOWN_RE = re.compile(
    r"\b(?:para\s+quem|com\s+quem|quem\s+devo|duvidas?|contato|falar|escrevo|e-?mail)\b"
)


def is_breakdown_request(question: str) -> bool:
    """
    True se a pergunta pede o detalhamento por eixo das atividades
    complementares (direto ou via pergunta canônica do follow-up).
    Perguntas sobre contato/dúvidas seguem o fluxo normal.
    """
    q = _norm(question)
    if not _AC_CONTEXT_RE.search(q):
        return False
    if _NOT_BREAKDOWN_RE.search(q):
        return False
    return any(p.search(q) for p in _DETAIL_CUES_RES)


_AFFIRM_WORDS = frozenset({
    "sim", "s", "quero", "pode", "podes", "claro", "por", "favor", "pfv",
    "ok", "okay", "manda", "bora", "isso", "aceito", "beleza", "blz",
    "uhum", "aham", "detalha", "detalhe", "detalhar", "vai", "vamos",
    "ser", "gentileza", "otimo", "perfeito", "top", "traz", "traga", "mostra",
})
_AFFIRM_STRONG = frozenset({
    "sim", "s", "quero", "pode", "podes", "claro", "ok", "okay", "manda",
    "bora", "aceito", "beleza", "blz", "uhum", "aham", "detalha", "detalhe",
    "detalhar", "traz", "traga", "mostra", "pfv",
})


def is_affirmative_reply(message: str) -> bool:
    """
    True se a mensagem é um aceite curto e inequívoco da oferta.
    Conservador: qualquer palavra fora do vocabulário de aceite (ex.:
    "sim, mas quantas horas...") desqualifica - a pergunta segue o fluxo normal.
    """
    words = re.sub(r"[!?.,;:]+", " ", _norm(message)).split()
    if not words or len(words) > 5:
        return False
    if not all(w in _AFFIRM_WORDS for w in words):
        return False
    return any(w in _AFFIRM_STRONG for w in words)


_regulamento_cache: dict = {"loaded": False, "data": None}


def _load_regulamento() -> Optional[dict]:
    if _regulamento_cache["loaded"]:
        return _regulamento_cache["data"]
    _regulamento_cache["loaded"] = True
    try:
        with open(_REGULAMENTO_PATH, encoding="utf-8") as f:
            _regulamento_cache["data"] = json.load(f)
    except Exception:
        _regulamento_cache["data"] = None
    return _regulamento_cache["data"]


def build_breakdown_response() -> str:
    """
    Formata o detalhamento por eixo diretamente do regulamento estruturado.
    Retorna "" se o arquivo não estiver disponível (caller segue o fluxo normal).
    """
    data = _load_regulamento()
    if not data:
        return ""
    try:
        artigo3 = data["artigos"]["artigo_3"]
        eixos = artigo3["eixos"]
        tipos = data.get("tipos_atividades", {})
    except (KeyError, TypeError):
        return ""

    ac = tipos.get("AC", {})
    partes = [
        f"As {ac.get('carga_horaria_minima', '312 horas')} obrigatórias de "
        "Atividades Complementares (AC) do BCT se dividem em 3 eixos, e é "
        "obrigatório ter atividade nos três (mínimo de 1 hora em cada):",
        "",
    ]
    for key in sorted(eixos):
        eixo = eixos[key]
        limite = eixo.get("limite_horas", "")
        limite_txt = (
            f" - limite de {limite}" if limite and "não especificado" not in limite.lower()
            else " - sem limite específico de horas"
        )
        partes.append(f"**{eixo.get('nome', key)}**{limite_txt}")
        for atividade in eixo.get("atividades_aceitas", []):
            if isinstance(atividade, dict):
                tipo = atividade.get("tipo", "")
                desc = atividade.get("descricao", "")
                partes.append(f"- **{tipo}**: {desc}" if desc else f"- **{tipo}**")
            else:
                partes.append(f"- {atividade}")
        partes.append("")

    ace = tipos.get("ACE", {})
    if ace:
        partes.append(
            f"Além das AC, as {ace.get('nome_completo', 'Atividades Complementares Extensionistas')} "
            f"(ACE) têm caráter {ace.get('carater', 'eletivo').lower()}, de "
            f"{ace.get('carga_horaria_minima', '36 horas')} a "
            f"{ace.get('carga_horaria_maxima', '108 horas')}."
        )

    partes.append(
        "Guia prático da DAE (documentação aceita, submissão via SEI e formulários): "
        "https://dae-sjc.unifesp.br/materiais/atividades-complementares-bct"
    )

    fonte = data.get("titulo", "Regulamento de Atividades Complementares do BCT")
    aprovacao = data.get("data_aprovacao", "")
    partes.append("")
    partes.append(
        f"*Fonte: {fonte}" + (f", aprovado em {aprovacao}" if aprovacao else "") + ".*"
    )
    return "\n".join(partes)


def maybe_append_offer(question: str, response: str) -> str:
    """
    Anexa a oferta de detalhamento ao fim de respostas sobre atividades
    complementares. Não anexa quando a resposta JÁ é o detalhamento, quando a
    oferta já está presente, ou quando o regulamento não está disponível.
    """
    if not response or not response.strip():
        return response
    if OFFER_MARKER in response:
        return response
    if not is_ac_question(question) or is_breakdown_request(question):
        return response
    if _load_regulamento() is None:
        return response
    return f"{response.rstrip()}\n\n{FOLLOWUP_OFFER}"
