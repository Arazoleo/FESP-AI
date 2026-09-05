"""
Sugestões de follow-up exibidas como botões após cada resposta.

Generalização da oferta de atividades complementares: para intents com termo
resolvido, o frontend recebe até 3 perguntas prontas, clicáveis, que continuam
a conversa sem o aluno digitar.
"""

from typing import List

from .atividades_complementares import (
    OFFER_MARKER,
    BREAKDOWN_CANONICAL_QUESTION,
)

_BY_INTENT = {
    "prerequisite_chain": [
        "O que {t} desbloqueia?",
        "Quem leciona {t}?",
        "Qual a ementa de {t}?",
    ],
    "dependents": [
        "Quais os pré-requisitos de {t}?",
        "Quem leciona {t}?",
    ],
    "recommended_before": [
        "Quais os pré-requisitos de {t}?",
        "Qual a ementa de {t}?",
    ],
    "ementa_disciplina": [
        "Quais os pré-requisitos de {t}?",
        "Quem leciona {t}?",
    ],
    "discipline_docentes": [
        "Qual a ementa de {t}?",
        "Quais os pré-requisitos de {t}?",
    ],
    "eletivas_curso": [
        "Como funciona a matriz curricular de {t}?",
        "Quem é o coordenador de {t}?",
    ],
    "matriz_info": [
        "Quais as eletivas de {t}?",
        "Quem é o coordenador de {t}?",
    ],
    "todos_termos_curso": [
        "Quais as eletivas de {t}?",
        "Como funciona a matriz curricular de {t}?",
    ],
    "coordenador_curso": [
        "Como funciona a matriz curricular de {t}?",
        "Quais as eletivas de {t}?",
    ],
    "docente_info": [
        "Quais disciplinas {t} leciona?",
        "Quais as áreas de pesquisa de {t}?",
    ],
    "docente_disciplines": [
        "Qual o contato de {t}?",
    ],
}


_MINUSCULAS = frozenset({
    "de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "para",
})


def _display_term(term: str) -> str:
    t = (term or "").strip()
    if not t or not t.islower():
        return t
    if len(t) <= 4 and t.isalpha():
        return t.upper()
    palavras = []
    for i, p in enumerate(t.split()):
        if i > 0 and p in _MINUSCULAS:
            palavras.append(p)
        else:
            palavras.append(p.capitalize())
    return " ".join(palavras)


_DOCENTE_TEMPLATES = [
    "Quais disciplinas {t} leciona?",
    "Quais as áreas de pesquisa de {t}?",
    "Qual o contato de {t}?",
]


def _eh_docente(kg, term: str) -> bool:
    """Grounding: o termo é um PROFESSOR no grafo? (evita aplicar templates de
    disciplina — 'pré-requisitos de {t}' — a um nome de docente)."""
    if kg is None or not term:
        return False
    try:
        return bool(kg._find_docente_id(term))
    except Exception:
        return False


def suggest_followups(intent: str, term: str, response: str, kg=None) -> List[str]:
    sugestoes: List[str] = []
    if OFFER_MARKER in (response or ""):
        sugestoes.append(BREAKDOWN_CANONICAL_QUESTION)

    # Pós-auditoria/progresso: oferece o dossiê em PDF (fluxo guiado).
    if intent in ("ac_auditoria", "progresso", "ac_checklist"):
        sugestoes.append("Gerar meu relatório de progresso em PDF")

    t = _display_term(term)
    templates = _BY_INTENT.get(intent or "", [])
    # se o termo é um docente, usa templates de docente (não de disciplina)
    if t and _eh_docente(kg, term):
        templates = _DOCENTE_TEMPLATES
    if t and templates:
        for tmpl in templates:
            pergunta = tmpl.format(t=t)
            if pergunta.lower() not in (response or "").lower():
                sugestoes.append(pergunta)

    return sugestoes[:3]
