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


def suggest_followups(intent: str, term: str, response: str) -> List[str]:
    sugestoes: List[str] = []
    if OFFER_MARKER in (response or ""):
        sugestoes.append(BREAKDOWN_CANONICAL_QUESTION)

    t = _display_term(term)
    templates = _BY_INTENT.get(intent or "", [])
    if t and templates:
        for tmpl in templates:
            pergunta = tmpl.format(t=t)
            if pergunta.lower() not in (response or "").lower():
                sugestoes.append(pergunta)

    return sugestoes[:3]
