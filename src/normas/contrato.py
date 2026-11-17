"""
Contrato de resposta para respostas com prova.

A resposta do motor sai de um texto determinístico montado a partir das
afirmações provadas (`afirmacoes`). Se um LLM reescrever esse texto para soar
natural, a reescrita só é aceita se:

- mantém os valores provados que respondem à pergunta (períodos, atraso,
  a UC em questão);
- não introduz período nem número de semestres que a prova não contém;
- mantém o aviso das suposições quando a prova depende de premissa.

Senão volta o texto determinístico. É o lado "Evaluate" para respostas
simbólicas: a checagem é contra o conjunto de átomos derivados, não contra
similaridade de texto.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Dict, Iterable, List, Optional, Tuple

_PERIODO = re.compile(r"\b(20\d{2})\s*/\s*([12])\b")
_SEMESTRES = re.compile(r"\b(\d+)\s+semestres?\b")
_SUPOSICAO = ("supond", "assumind", "considerand", "premissa", "suposi")


def _fold(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _strings(x) -> Iterable[str]:
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _strings(v)


def _periodos(texto: str) -> set:
    return {f"{a}/{s}" for a, s in _PERIODO.findall(texto or "")}


def verificar(afirmacoes: Dict, texto: str) -> Dict:
    violacoes: List[str] = []
    provados = set()
    for s in _strings(afirmacoes):
        provados |= _periodos(s)
    ditos = _periodos(texto)
    for p in sorted(ditos - provados):
        violacoes.append(f"período sem prova: {p}")
    for chave in ("formatura_hipotese", "formatura_base"):
        v = afirmacoes.get(chave)
        if v and afirmacoes.get("efeito") == "atrasa" and v not in ditos:
            violacoes.append(f"omitiu {chave}: {v}")
    if afirmacoes.get("efeito") == "nao_atrasa" and afirmacoes.get("formatura_hipotese") not in ditos:
        violacoes.append(f"omitiu formatura_hipotese: {afirmacoes.get('formatura_hipotese')}")
    atraso = afirmacoes.get("atraso")
    for n in _SEMESTRES.findall(texto or ""):
        if atraso is None or int(n) != atraso:
            violacoes.append(f"número de semestres sem prova: {n}")
    if atraso and atraso > 0 and str(atraso) not in re.findall(r"\d+", texto or ""):
        violacoes.append(f"omitiu o atraso: {atraso}")
    uc = afirmacoes.get("uc")
    if uc and not all(w in _fold(texto).split() for w in _fold(uc).split() if len(w) > 3):
        violacoes.append(f"não cita a UC: {uc}")
    if afirmacoes.get("premissas") and not any(m in _fold(texto) for m in _SUPOSICAO):
        violacoes.append("omitiu as suposições")
    return {"ok": not violacoes, "violacoes": violacoes}


def responder(afirmacoes: Dict, texto_deterministico: str,
              reescrever: Optional[Callable[[str], str]] = None) -> Tuple[str, Dict]:
    """Texto final + diagnóstico. Sem `reescrever`, o determinístico (que
    satisfaz o contrato por construção)."""
    if reescrever is None:
        return texto_deterministico, {"reescrita": False, "ok": True, "violacoes": []}
    try:
        candidato = (reescrever(texto_deterministico) or "").strip()
    except Exception as e:
        return texto_deterministico, {"reescrita": False, "ok": False, "violacoes": [str(e)]}
    v = verificar(afirmacoes, candidato)
    if v["ok"]:
        return candidato, {"reescrita": True, **v}
    return texto_deterministico, {"reescrita": False, **v}
