"""
Loop de segunda chance (retry-on-miss).

Quando a resposta final indica falha ("não encontrei", "não tenho esse dado",
"não consegui identificar") e ainda não houve retry, o pipeline re-roteia UMA
vez para um agente alternativo (heurística de fallback abaixo). A segunda
resposta só substitui a primeira se NÃO casar os padrões de falha.

Módulo propositalmente sem dependências (re/unicodedata) para permitir teste
offline sem langgraph/langchain (test_second_chance.py).
"""

import re
import unicodedata
from typing import Callable, Optional


# Padrões de falha (aplicados sobre o texto minúsculo e sem acentos)
_MISS_PATTERNS = [
    r"nao\s+encontrei",
    r"nao\s+tenho\s+esse\s+dado",
    r"nao\s+consegui\s+identificar",
]
_MISS_RES = [re.compile(p) for p in _MISS_PATTERNS]


def _fold(text: str) -> str:
    """minúsculas + sem acentos, para casamento case/acento-insensitive."""
    lowered = (text or "").lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )


def is_miss_response(text: str) -> bool:
    """True se a resposta indica que o agente não encontrou a informação."""
    folded = _fold(text)
    if not folded.strip():
        return False
    return any(p.search(folded) for p in _MISS_RES)


# Heurística de fallback: quem tenta em seguida quando o agente falhou.
#   symbolic_kg → web_sjc → fallback (RAG genérico)
#   agentes especialistas → web_sjc
# "conversa", "meta" e "fallback" não têm segunda chance (nada melhor a tentar).
RETRY_FALLBACK = {
    "symbolic_kg": "web_sjc",
    "disciplinas": "web_sjc",
    "docentes": "web_sjc",
    "cursos": "web_sjc",
    "regimentos": "web_sjc",
    "montar_grade": "web_sjc",
    "noticias": "web_sjc",
    "web_sjc": "fallback",
}


def fallback_agent_for(agent: str) -> Optional[str]:
    """Agente alternativo para a segunda chance (None = sem retry)."""
    return RETRY_FALLBACK.get(agent)


def run_with_second_chance(
    invoke: Callable[[dict], dict],
    initial_state: dict,
    telemetry_incr: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Executa o pipeline com o loop de segunda chance.

    `invoke`: função estado→estado (pipeline.invoke).
    Retorna o estado final (o da 2ª tentativa apenas se ela recuperou).
    Telemetria: "retry_recuperado" / "retry_sem_sucesso".
    """
    first = invoke(initial_state)
    if initial_state.get("retry_count", 0) > 0:
        return first
    if not is_miss_response(first.get("response", "")):
        return first

    failed_agent = first.get("active_agent", "")
    retry_agent = fallback_agent_for(failed_agent)
    if not retry_agent or retry_agent == failed_agent:
        return first

    retry_state = {
        **initial_state,
        "retry_count": 1,
        "forced_agent": retry_agent,
    }
    try:
        second = invoke(retry_state)
    except Exception:
        return first

    if second.get("response", "").strip() and not is_miss_response(second["response"]):
        if telemetry_incr:
            telemetry_incr("retry_recuperado")
        return {**second, "retry_from_agent": failed_agent, "retry_count": 1}
    if telemetry_incr:
        telemetry_incr("retry_sem_sucesso")
    return {**first, "retry_count": 1}
