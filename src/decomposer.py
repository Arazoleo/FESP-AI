"""
Decomposição de perguntas compostas ("duas ou mais coisas no mesmo prompt").

A decisão de dividir é SEMPRE do LLM (semântica, não lexical): o gate
pode_ser_composta é apenas um filtro barato de alto recall para não gastar uma
chamada de LLM em perguntas que não têm como ser compostas. Cada subpergunta
autocontida roda a pipeline completa e acha o próprio agente; a composição
preserva fontes e artefatos de cada parte.
"""

import json
import re
from typing import Dict, List, Optional

_SEPARADORES = (
    " e ", ", ", "; ", " tambem ", " também ", " alem ", " além ",
    " e tambem", " e também", " ainda ",
)


def pode_ser_composta(texto: str) -> bool:
    t = (texto or "").strip()
    if len(t) < 25:
        return False
    if t.count("?") >= 2:
        return True
    baixo = f" {t.lower()} "
    return any(s in baixo for s in _SEPARADORES)


_PROMPT = """Voce analisa a pergunta de um aluno a um assistente academico da UNIFESP e decide se ela contem MAIS DE UM pedido independente de informacao.

DIVIDA apenas quando a pergunta pede coisas de tipos diferentes, que exigem respostas separadas. Exemplo: "quais os pre-requisitos de Compiladores e quem leciona?" pede a cadeia de pre-requisitos E o docente - sao dois pedidos.

NAO DIVIDA quando:
- e um unico pedido com uma lista de itens ("estou cursando X, Y e Z", "tenho 40h de monitoria e 20h de palestras, quanto vale de AC?", "posso me matricular em X e Y?")
- e uma comparacao ("qual a diferenca entre X e Y?")
- o "e" faz parte do nome de uma disciplina ou curso ("Ciencia, Tecnologia e Sociedade")
- os pedidos sao o mesmo tipo de informacao sobre a mesma entidade

Cada subpergunta deve ser AUTOCONTIDA: repita a entidade por extenso ("quem leciona Compiladores?", nunca "quem leciona?"). Maximo de 3 subperguntas, na ordem original.

PERGUNTA DO ALUNO: {question}

Responda APENAS com JSON valido (sem markdown):
{{"composta": true|false, "subperguntas": ["...", "..."]}}

JSON:"""


def _extrair_json(raw: str) -> Optional[dict]:
    if not raw:
        return None
    texto = re.sub(r"```(?:json)?", "", str(raw)).strip()
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (ValueError, TypeError):
        return None


def decompor_pergunta(question: str, llm, telemetry_incr=None) -> Optional[List[str]]:
    if llm is None or not question:
        return None
    if telemetry_incr:
        telemetry_incr("decompose_llm_call")
    try:
        resp = llm.invoke(_PROMPT.format(question=question.strip()))
        raw = getattr(resp, "content", None) or str(resp)
    except Exception:
        return None
    dados = _extrair_json(raw)
    if not dados or not dados.get("composta"):
        if telemetry_incr:
            telemetry_incr("decompose_nao_composta")
        return None
    subs = [
        s.strip()
        for s in (dados.get("subperguntas") or [])
        if isinstance(s, str) and len(s.strip()) >= 8
    ][:3]
    if len(subs) < 2:
        return None
    if telemetry_incr:
        telemetry_incr("decompose_split")
    return subs


def combinar_respostas(subs: List[str], resultados: List[Dict]) -> Dict:
    partes = []
    fontes: List[str] = []
    for i, (sub, r) in enumerate(zip(subs, resultados), 1):
        corpo = (r.get("response") or "").strip()
        partes.append(f"**{i}. {sub}**\n\n{corpo}")
        for f in r.get("sources") or []:
            if f not in fontes:
                fontes.append(f)

    agentes = [r.get("active_agent") or "fallback" for r in resultados]
    agente = agentes[0] if len(set(agentes)) == 1 else "multi"

    def primeiro(chave):
        for r in resultados:
            if r.get(chave):
                return r[chave]
        return None

    confiancas = [r.get("confidence") for r in resultados if r.get("confidence") is not None]
    return {
        "response": "\n\n---\n\n".join(partes),
        "active_agent": agente,
        "intent": "multi_intent",
        "term": "",
        "confidence": min(confiancas) if confiancas else 0.0,
        "context": "",
        "sources": fontes,
        "plan_request": primeiro("plan_request"),
        "graph_data": primeiro("graph_data"),
        "list_data": primeiro("list_data"),
        "ac_data": primeiro("ac_data"),
        "suggestions": primeiro("suggestions"),
    }
