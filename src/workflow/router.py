"""
Router: mapeia intents classificados aos agentes especializados.
"""

from typing import Dict, Optional


# Intents que o Knowledge Graph pode responder COMPLETAMENTE sem precisar do LLM.
# Para esses intents, o pipeline usa o KG diretamente (atalho neurossimbólico),
# eliminando latência e risco de alucinação para perguntas estruturadas.
SYMBOLIC_DIRECT_INTENTS: frozenset = frozenset({
    # Matrizes curriculares e estrutura dos cursos
    "listar_cursos",
    "coordenador_curso",
    "disciplinas_termo",
    "todos_termos_curso",
    "eletivas_curso",
    "matriz_info",
    # Pré-requisitos e dependências (o KG tem a cadeia completa)
    "prerequisite_chain",
    "dependents",
    # Quem leciona / docente leciona disciplina (resposta sim/não + lista)
    "discipline_docentes",
    "docente_leciona_disciplina",
    "docentes_by_area",
})

# Resposta fixa para perguntas meta sobre capacidades do sistema
META_CAPABILITIES_RESPONSE = """Sim. Tenho acesso a informações da UNIFESP ICT sobre:

- **Disciplinas:** pré-requisitos, ementas, carga horária, docentes e bibliografia
- **Docentes:** contato (email, sala), áreas de pesquisa e disciplinas que lecionam
- **Cursos:** matriz curricular, disciplinas por termo, eletivas
- **Regimentos e normas:** atividades complementares, trancamento, aprovação, FAQs

Pergunte sobre qualquer um desses temas em português."""


def get_meta_capability_response(question_lower: str) -> Optional[str]:
    """Se a pergunta for meta sobre capacidades do sistema, retorna a resposta fixa; senão None."""
    meta_phrases = [
        "você tem acesso",
        "tem acesso a",
        "tem acesso às",
        "você tem ementa",
        "tem ementa",
        "quais informações você tem",
        "o que você sabe",
        "o que você consegue",
        "você consegue",
        "quais dados você",
        "que tipo de informação",
        "do que você dispõe",
    ]
    if any(p in question_lower for p in meta_phrases) and len(question_lower) < 120:
        return META_CAPABILITIES_RESPONSE
    return None

# Mapeamento de intent → agente especializado
INTENT_TO_AGENT: Dict[str, str] = {
    # ── Docentes ──────────────────────────────────────────
    "docente_info": "docentes",
    "docente_areas": "docentes",
    "docente_disciplines": "docentes",
    "discipline_docentes": "docentes",
    "docentes_by_area": "docentes",
    "docente_leciona_disciplina": "docentes",
    # ── Cursos / Matrizes Curriculares ────────────────────
    "disciplinas_termo": "cursos",
    "todos_termos_curso": "cursos",
    "matriz_info": "cursos",
    "eletivas_curso": "cursos",
    "listar_cursos": "cursos",
    "coordenador_curso": "cursos",
    # ── Disciplinas / Pré-requisitos ──────────────────────
    "prerequisite_chain": "disciplinas",
    "dependents": "disciplinas",
    "ementa_disciplina": "disciplinas",
    # ── Regimentos / Normas ───────────────────────────────
    "artigos_sobre": "regimentos",
    "faqs": "regimentos",
}

# Keywords que forçam o agente de regimentos independente do intent
REGIMENTO_FORCE_KEYWORDS = [
    "regimento", "regulamento", "norma", "artigo", "resolucao",
    "evacuacao", "incendio", "seguranca", "faq", "perguntas frequentes",
    "atividade complementar", "atividades complementares",
    "trancamento", "aprovacao", "reprovacao",
]

# Keywords que forçam o agente de cursos sequenciais
CURSOS_SEQ_KEYWORDS = [
    "sequencial", "sequenciais", "certificado",
    "fundamentos de ciência", "fundamentos de ciencia",
    "métodos estatísticos", "metodos estatisticos",
    "economia e mercados", "química aplicada", "quimica aplicada",
    "desenvolvimento de games", "jogos digitais",
]

# Frases que indicam claramente query sobre DOCENTES → sempre Agente Docentes
DISCIPLINE_DOCENTES_PHRASES = [
    # "quem leciona X?" / "quais docentes dão X?"
    "quais docentes",
    "quais professores",
    "quem leciona",
    "quem ensina",
    "quem ministra",
    "quem da aula",
    "quem dá aula",
    "que professor",
    "que professora",
    "professores de",
    "docentes de",
    "professores da",
    "docentes da",
    "professores do",
    "docentes do",
    # "quais disciplinas X leciona?" — o sujeito da ação é um docente
    "costuma lecionar",
    "costuma ensinar",
    "disciplinas que ele",
    "disciplinas que ela",
    "disciplinas lecionadas por",
    "disciplinas ministradas por",
    "disciplinas do professor",
    "disciplinas da professora",
]

# Frases que indicam consulta de pré-requisitos → sempre Agente Disciplinas
PREREQUISITE_PHRASES = [
    "pre-requisito", "pre requisito", "prerequisito",
    "pré-requisito", "pré requisito",
    "antes de cursar", "antes de fazer",
    "preciso cursar", "preciso de",
    "depende de", "dependem de",
]

# Frases que indicam info/ementa/descrição de DISCIPLINA → Agente Disciplinas (evita ir para Docentes)
DISCIPLINE_INFO_PHRASES = [
    "fale mais sobre",
    "me fale mais",
    "me fale sobre",
    "fale mais",
    "fale sobre a disciplina",
    "fale sobre a matéria",
    "o que sabe sobre",
    "o que vc sabe sobre",
    "qual a ementa",
    "ementa de",
    "ementa da",
    "o que é a disciplina",
    "descreva a disciplina",
    "conte mais sobre a disciplina",
]


def route_intent(intent: str, question_lower: str) -> str:
    """
    Determina qual agente deve tratar a pergunta.
    Aplica overrides por keywords antes de consultar o mapa de intents.
    Ordem de prioridade:
    1. Docentes (frases específicas como "quais docentes dão X")
    2. Pré-requisitos (frases específicas como "pré-requisitos de X")
    3. Regimentos (keywords institucionais)
    4. Cursos sequenciais
    5. Mapa de intents classificados
    6. Fallback
    """
    # Override para "quem leciona / quais docentes de X"
    if any(kw in question_lower for kw in DISCIPLINE_DOCENTES_PHRASES):
        return "docentes"

    # Override para pré-requisitos / dependências
    if any(kw in question_lower for kw in PREREQUISITE_PHRASES):
        return "disciplinas"

    # Override para "fale mais sobre [disciplina]", ementa, descrição de disciplina
    if any(kw in question_lower for kw in DISCIPLINE_INFO_PHRASES):
        return "disciplinas"

    # Override para keywords de regimento
    if any(kw in question_lower for kw in REGIMENTO_FORCE_KEYWORDS):
        return "regimentos"

    # Override para cursos sequenciais
    if any(kw in question_lower for kw in CURSOS_SEQ_KEYWORDS):
        return "cursos"

    # Lookup no mapa de intents classificados pelo IntentClassifier
    if intent in INTENT_TO_AGENT:
        return INTENT_TO_AGENT[intent]

    # Fallback para perguntas gerais
    return "fallback"
