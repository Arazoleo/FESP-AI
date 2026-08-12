"""
Debate com juiz simbólico.

Para perguntas que o roteamento não classificou (caminho de fallback), dois
candidatos respondem em paralelo e o Knowledge Graph arbitra: vence a resposta
com mais claims verificados e menos violações. É o padrão de debate
multiagente, mas com árbitro determinístico - alinhado à tese do FESP-AI de
que a decisão final nunca fica com um LLM.

Puro (sem dependências de langchain) para teste offline.
"""

from typing import Callable, Dict, List, Optional

from .second_chance import is_miss_response

PESO_FATO = 2
PESO_VIOLACAO = 3
PENALIDADE_MISS = 100


def pontuar(candidato: Dict) -> int:
    """
    Score simbólico de uma resposta candidata.

    fatos_verificados e violacoes vêm do SymbolicValidator; miss zera a
    disputa (resposta que admite não saber não pode vencer uma que sabe).
    """
    resposta = candidato.get("response") or ""
    if not resposta.strip():
        return -PENALIDADE_MISS
    score = 0
    score += PESO_FATO * len(candidato.get("fatos_verificados") or [])
    score -= PESO_VIOLACAO * len(candidato.get("violacoes") or [])
    if is_miss_response(resposta):
        score -= PENALIDADE_MISS
    return score


def julgar(candidatos: List[Dict]) -> Dict:
    """
    Escolhe o vencedor entre 2+ candidatos já pontuáveis. Empate mantém a
    ordem (primeiro candidato vence). Retorna o candidato vencedor com o
    veredito anexado.
    """
    if not candidatos:
        return {}
    pontuados = [(pontuar(c), i, c) for i, c in enumerate(candidatos)]
    pontuados.sort(key=lambda t: (-t[0], t[1]))
    melhor_score, _, vencedor = pontuados[0]
    veredito = {
        "vencedor": vencedor.get("agente", "?"),
        "scores": {
            c.get("agente", f"c{i}"): s for s, i, c in sorted(pontuados, key=lambda t: t[1])
        },
        "empate": len(pontuados) > 1 and pontuados[0][0] == pontuados[1][0],
    }
    return {**vencedor, "veredito": veredito}


def debater(
    pergunta: str,
    respondentes: List[Dict],
    validar: Optional[Callable[[str], Dict]] = None,
    telemetry_incr: Optional[Callable[[str], None]] = None,
) -> Dict:
    """
    Roda o debate: cada respondente é {"agente": str, "responder": fn() -> Dict}
    com o Dict contendo response/sources/context. `validar(response)` devolve
    {"fatos_verificados": [...], "violacoes": [...]} via juiz simbólico.
    """
    candidatos = []
    for r in respondentes:
        try:
            resultado = r["responder"]()
        except Exception:
            continue
        cand = {
            "agente": r.get("agente", "?"),
            "response": resultado.get("response", ""),
            "sources": resultado.get("sources", []),
            "context": resultado.get("context", ""),
        }
        if validar and cand["response"]:
            try:
                laudo = validar(cand["response"]) or {}
                cand["fatos_verificados"] = laudo.get("fatos_verificados") or []
                cand["violacoes"] = laudo.get("violacoes") or []
            except Exception:
                pass
        candidatos.append(cand)

    if not candidatos:
        return {}
    if len(candidatos) == 1:
        return candidatos[0]
    if telemetry_incr:
        telemetry_incr("debate_executado")
    vencedor = julgar(candidatos)
    if telemetry_incr and vencedor.get("veredito"):
        telemetry_incr(f"debate_vencedor_{vencedor['veredito']['vencedor']}")
    return vencedor
