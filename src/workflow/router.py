"""
Router: mapeia intents classificados aos agentes especializados.
"""

import re
import unicodedata
from typing import Dict, Optional


def _strip_accents(s: str) -> str:
    """Remove acentos para casamento robusto de frases (matérias == materias)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _phrase_in(phrase: str, text: str) -> bool:
    """
    Casamento de frase com word-boundary — nunca por substring.

    Por substring, "disciplina" casava dentro de "interdisciplinar", "ei"
    dentro de "aproveitamento" e "nde" dentro de "aprende", roteando errado.
    """
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _any_phrase(phrases, text: str) -> bool:
    return any(_phrase_in(p, text) for p in phrases)


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
    "co_prerequisite",
    "critical_disciplines",
    # Planejamento de trajetória (BFS topológico no DAG de pré-requisitos)
    "trajectory_planning",
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


# ── Conversa social (small talk) → Agente Conversacional ──────────────────────
# Saudações isoladas (uma palavra)
_GREETING_WORDS = frozenset({
    "oi", "ola", "olá", "eai", "opa", "alo", "alô", "hey", "hi", "ei",
})
# Frases de saudação / abertura
_GREETING_PHRASES = [
    "bom dia", "boa tarde", "boa noite", "e ai", "e aí", "tudo bem",
    "tudo bom", "tudo certo", "como vai", "como voce esta", "como você está",
    "como vc esta", "beleza", "blz", "salve",
]
# Agradecimentos
_THANKS_PHRASES = [
    "obrigado", "obrigada", "obg", "valeu", "vlw", "agradeco", "agradeço",
    "grato", "grata",
]
# Despedidas
_FAREWELL_PHRASES = [
    "tchau", "ate logo", "até logo", "ate mais", "até mais", "ate breve",
    "até breve", "adeus", "falou", "flw", "ate a proxima", "até a próxima",
]
# Perguntas sobre a identidade/natureza do assistente
_IDENTITY_PHRASES = [
    "quem e voce", "quem é você", "quem e vc", "qual seu nome", "qual o seu nome",
    "voce e um robo", "você é um robô", "voce e uma ia", "você é uma ia",
    "voce e humano", "você é humano", "o que voce e", "o que você é",
    "como voce funciona", "como você funciona", "voce e real", "você é real",
]
# Palavras que denotam pedido de informação — desqualificam "conversa pura"
_INFO_KEYWORDS = [
    "disciplina", "materia", "matéria", "professor", "docente", "curso",
    "pre-requisito", "pré-requisito", "pre requisito", "prerequisito",
    "ementa", "carga", "matriz", "termo", "credito", "crédito",
    "regimento", "norma", "artigo", "coordenador",
]


def is_conversational(question_lower: str) -> bool:
    """
    True quando a mensagem é conversa social pura (saudação, agradecimento,
    despedida ou pergunta sobre a identidade do assistente) — e não um pedido
    de informação. Conservador: mensagens longas ou com termos informativos
    seguem para os agentes especializados / fallback.
    """
    q = question_lower.strip().strip("?!.,;:").strip()
    if not q:
        return False
    words = q.split()

    # Identidade do assistente: sempre conversacional, independente do tamanho.
    if any(p in q for p in _IDENTITY_PHRASES):
        return True

    # Saudação isolada (uma palavra).
    if q in _GREETING_WORDS:
        return True

    # Se há claramente um pedido de informação, não é conversa pura.
    if any(kw in q for kw in _INFO_KEYWORDS):
        return False

    # Saudação / agradecimento / despedida em mensagens curtas.
    # Word-boundary obrigatório: por substring, "ei" casava dentro de
    # "aproveitamento" e "oi" dentro de "coisa", roteando pergunta real
    # para o agente de conversa.
    social = _GREETING_PHRASES + _THANKS_PHRASES + _FAREWELL_PHRASES + list(_GREETING_WORDS)
    if len(words) <= 6 and any(
        re.search(rf"\b{re.escape(p)}\b", q) for p in social
    ):
        return True

    return False


# ── Pedido de montar a grade / planejar trajetória → Agente MontarGrade ───────
_MONTAR_GRADE_PHRASES = [
    "montar grade", "monta grade", "monte grade",
    "montar minha grade", "monta minha grade", "monte minha grade",
    "montar a grade", "monta a grade", "monte a grade",
    "planejar grade", "planejar minha grade", "planeje minha grade",
    "plano de estudos", "plano de estudo", "planejamento de estudos",
    "montar trajetoria", "montar trajetória", "monte minha trajetoria",
    "monte minha trajetória", "planejar trajetoria", "planejar trajetória",
    "planejar minha trajetoria", "planejar minha trajetória",
    "que materias devo cursar", "quais materias devo cursar",
    "que disciplinas devo cursar", "quais disciplinas devo cursar",
    "como me formar", "para me formar", "pra me formar",
    "ordem das disciplinas", "ordem das materias",
    "que materias posso fazer", "quais materias posso fazer",
    "montar meu semestre", "planejar meus semestres",
]


def is_montar_grade(question_lower: str) -> bool:
    """True se a mensagem pede para montar a grade / planejar a trajetória."""
    q = _strip_accents(question_lower)
    return any(_strip_accents(p) in q for p in _MONTAR_GRADE_PHRASES)


# ── Pedido de notícias / novidades da UNIFESP → Agente Notícias ───────────────
_NOTICIAS_PHRASES = [
    "noticia", "noticias", "novidade", "novidades",
    "o que esta acontecendo", "o que ta acontecendo", "o que aconteceu",
    "o que esta rolando", "o que ta rolando", "o que tem de novo", "o que ha de novo",
    "ultimas noticias", "acontecendo na unifesp", "acontecendo no campus",
    "eventos da unifesp", "eventos do campus", "edital", "editais",
    "congresso academico", "mural de noticias",
]


def is_noticias(question_lower: str) -> bool:
    """True se a mensagem pede notícias/novidades/eventos da UNIFESP."""
    q = _strip_accents(question_lower)
    return any(p in q for p in _NOTICIAS_PHRASES)


# ── Perguntas institucionais sobre o campus → Agente Web SJC (site completo) ───
_WEB_SJC_PHRASES = [
    "secretaria", "secretaria academica", "ingresso", "como ingressar",
    "selecao interna", "selecao externa", "transferencia", "reingresso",
    "biblioteca", "contato", "contatos", "telefone", "endereco", "onde fica",
    "como chego", "horario de atendimento", "atendimento", "fale conosco",
    "direcao", "diretor", "diretora", "congregacao", "departamento",
    "pos-graduacao", "pos graduacao", "pos-graduacao e pesquisa", "mestrado",
    "doutorado", "napcem", "estagio", "bolsa", "bolsas", "monitoria",
    "orgaos assessores", "comissao", "camara de graduacao", "calendario academico",
    "apresentacao do campus", "sobre o campus", "sobre o ict", "mapa do site",
    "servicos", "restaurante universitario", "bandejao", "assistencia estudantil",
    # Páginas de curso do site (ex.: BCT) — integralização, PPC, comissões
    # (as FAQs das páginas de curso detalham extensionistas; o regimento não)
    "extensionista", "extensionistas",
    "integralizar", "integralizacao", "projeto pedagogico", "ppc",
    "pos-bct", "pos bct", "matriz de transicao", "comissao de curso",
    "nucleo docente", "nde", "ex-officio", "ex officio",
    # Procedimentos da secretaria (páginas em /graduacao-todos)
    "atestado", "diploma", "aproveitamento de estudos", "cracha", "crachá",
    "historico escolar", "cancelamento de matricula", "colacao de grau",
    "atualizacao de dados", "certificado de conclusao",
    "rematricula", "matriz horaria", "cancelamento", "dados cadastrais",
    "trancamento de matricula", "prorrogacao", "revisao de prova",
    "ausencias e licencas", "licenca medica", "licencas medicas",
    "peticionamento", "catalogo de disciplinas", "ementario", "oferta de ucs",
    "passe escolar", "trocar de turma", "trocar de turno",
    "troca de turma", "troca de turno",
    # TCC e páginas de curso (TCC I/II como disciplina fica nas exclusões)
    "tcc", "trabalho de conclusao", "aluno especial",
    # Órgãos, serviços e infraestrutura do campus (/institucional, /todos-institucional)
    "caltae", "sicad", "gtae", "fapesp", "espaco fisico", "atos normativos",
    "agenda do ict", "agenda do campus", "gestao de contratos", "convenios",
    "desenvolvimento tecnologico", "inovacao tecnologica",
    # Serviços da biblioteca (páginas em /biblioteca)
    "sala de estudo", "salas de estudo", "plagio", "similaridade",
    "pergamum", "ficha catalografica", "repositorio institucional",
    "doacao de livros", "emprestimo de livro", "devolucao",
    # DAE — Divisão de Assuntos Educacionais (dae-sjc.unifesp.br)
    "dae", "assuntos educacionais", "apoio ao estudante",
    "materiais de aula", "materiais de apoio", "material de apoio",
    "dicas de estudo", "dicas para ingressantes",
    "quadro resumo da graduacao", "quadro geral da graduacao",
    "plano de rematricula", "minicurso", "minicursos",
    "orientacao academica", "relatorio de progresso", "progresso academico",
    "aditamento", "aditamentos", "rescisao",
]


# Se a pergunta cita professor/disciplina, deixe os agentes especialistas tratarem
# (evita "contato do PROFESSOR X" cair no agente do site por causa de "contato").
_WEB_SJC_EXCLUDE = [
    "professor", "professora", "docente", "disciplina", "materia", "ementa",
    "pre-requisito", "pre requisito", "prerequisito", "pré-requisito",
    "pre-requisitos", "pre requisitos", "prerequisitos",
    "leciona", "ministra", "carga horaria", "carga horária",
    # TCC I/II são disciplinas do KG — perguntas sobre elas ficam com os
    # agentes especialistas; "tcc" genérico (regras/curso) segue para o site
    "tcc i", "tcc ii", "tcc 1", "tcc 2",
    # Perguntas sobre normas citando o documento → agente de regimentos
    "regimento", "regulamento", "norma", "artigo", "resolucao",
]


def is_web_sjc(question_lower: str) -> bool:
    """True se a pergunta é institucional sobre o campus (coberta pelo site)."""
    q = _strip_accents(question_lower)
    if _any_phrase([_strip_accents(e) for e in _WEB_SJC_EXCLUDE], q):
        return False
    return _any_phrase(_WEB_SJC_PHRASES, q)


# ── Pergunta descritiva sobre um CURSO → página do curso no site ──────────────
# "O que é o BCT?", "Como funciona a Engenharia Biomédica?", "Me fale sobre o BCC"
_COURSE_OVERVIEW_PATTERNS = [
    r"^o\s+que\s+e\s+(?:o\s+curso\s+(?:de\s+)?|o\s+|a\s+)?(.+?)\s*\??$",
    r"^como\s+(?:funciona|e)\s+(?:o\s+curso\s+(?:de\s+)?|o\s+|a\s+)?(.+?)\s*\??$",
    r"^(?:me\s+)?fale\s+(?:mais\s+)?sobre\s+(?:o\s+curso\s+(?:de\s+)?|o\s+|a\s+)?(.+?)\s*\??$",
]


def is_course_overview(question_lower: str, kg) -> bool:
    """
    True quando a pergunta é descritiva ("o que é / como funciona / fale sobre")
    e a entidade resolve para um CURSO no Knowledge Graph — e não para uma
    disciplina. Nesse caso a melhor fonte é a página do curso no site do campus
    (WebSjcAgent), não o agente de disciplinas.

    Decisão simbólica: consulta o KG para desambiguar curso × disciplina.
    """
    if kg is None:
        return False
    q = _strip_accents(question_lower.strip())
    for pattern in _COURSE_OVERVIEW_PATTERNS:
        m = re.match(pattern, q)
        if not m:
            continue
        entidade = m.group(1).strip().strip("?.! ")
        if not entidade or len(entidade) < 2:
            continue
        try:
            # Disciplina: match EXATO (nome/sigla). O fallback por substring do
            # _find_node é greedy demais aqui — "Engenharia Biomédica" (curso)
            # casaria com "Introdução à Engenharia Biomédica" (disciplina).
            norm = kg._normalize_text(entidade)
            disc_id = kg._index_by_name.get(norm) or kg._index_by_sigla.get(norm)
            if disc_id and kg.graph.nodes[disc_id].get("tipo") == "disciplina":
                return False  # "O que é Teoria dos Grafos?" → agente de disciplinas
            if kg._find_node(entidade, "curso") or kg._find_node(entidade, "matriz_curricular"):
                return True
        except Exception:
            return False
    return False


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
    # ── Disciplinas / Pré-requisitos / Trajetória ─────────
    "prerequisite_chain": "disciplinas",
    "dependents": "disciplinas",
    "co_prerequisite": "disciplinas",
    "critical_disciplines": "disciplinas",
    "ementa_disciplina": "disciplinas",
    "trajectory_planning": "disciplinas",
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
    # "me fale sobre o professor X" / "quem é a professora Y" — sujeito é docente
    "sobre o professor",
    "sobre a professora",
    "sobre o docente",
    "sobre a docente",
    "quem é o professor",
    "quem é a professora",
    "quem e o professor",
    "quem e a professora",
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
    "fale sobre",
    "fale mais",
    "ementa",
    "fale sobre a disciplina",
    "fale sobre a matéria",
    "o que sabe sobre",
    "o que vc sabe sobre",
    "qual a ementa",
    "ementa de",
    "ementa da",
    "ementa do",
    "a ementa",
    "tem ementa",
    "o que é a disciplina",
    "descreva a disciplina",
    "conte mais sobre a disciplina",
]


def phrase_override(question_lower: str, current_agent: str = "") -> Optional[str]:
    """
    Overrides de alta precisão por frase. Retorna o agente forçado ou None.

    Fonte única de verdade para os overrides — usada tanto por route_intent
    (caminho sem embeddings) quanto pelo pipeline (por cima do roteamento por
    embeddings, substituindo correções hardcoded pontuais).

    Ordem de prioridade:
    1. Docentes (frases como "quais docentes dão X", "sobre a professora Y")
    2. Pré-requisitos → disciplinas
    3. Info/ementa de disciplina → disciplinas
       (quando vindo do embedding, só corrige a partir de docentes — não
        sobrescreve uma escolha explícita de cursos/regimentos)
    4. Regimentos (keywords institucionais)
    5. Cursos sequenciais
    """
    # Override para "quem leciona / quais docentes de X / sobre a professora Y"
    if _any_phrase(DISCIPLINE_DOCENTES_PHRASES, question_lower):
        return "docentes"

    # Override para pré-requisitos / dependências
    if _any_phrase(PREREQUISITE_PHRASES, question_lower):
        return "disciplinas"

    # Override para "fale mais sobre [disciplina]", ementa, descrição de disciplina
    if current_agent in ("", "docentes", "disciplinas") and _any_phrase(
        DISCIPLINE_INFO_PHRASES, question_lower
    ):
        return "disciplinas"

    # Override para keywords de regimento
    if _any_phrase(REGIMENTO_FORCE_KEYWORDS, question_lower):
        return "regimentos"

    # Override para cursos sequenciais
    if _any_phrase(CURSOS_SEQ_KEYWORDS, question_lower):
        return "cursos"

    return None


def route_intent(intent: str, question_lower: str) -> str:
    """
    Determina qual agente deve tratar a pergunta.
    Aplica overrides por frase antes de consultar o mapa de intents.
    """
    override = phrase_override(question_lower)
    if override:
        return override

    # Lookup no mapa de intents classificados pelo IntentClassifier
    if intent in INTENT_TO_AGENT:
        return INTENT_TO_AGENT[intent]

    # Fallback para perguntas gerais
    return "fallback"
