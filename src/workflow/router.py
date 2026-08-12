"""
Router: mapeia intents classificados aos agentes especializados.
"""

import json
import os
import re
import unicodedata
from collections import OrderedDict
from typing import Callable, Dict, Optional


def _strip_accents(s: str) -> str:
    """Remove acentos para casamento robusto de frases (matérias == materias)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _phrase_in(phrase: str, text: str) -> bool:
    """
    Casamento de frase com word-boundary - nunca por substring.

    Por substring, "disciplina" casava dentro de "interdisciplinar", "ei"
    dentro de "aproveitamento" e "nde" dentro de "aprende", roteando errado.
    """
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _any_phrase(phrases, text: str) -> bool:
    return any(_phrase_in(p, text) for p in phrases)


SYMBOLIC_DIRECT_INTENTS: frozenset = frozenset({
    "listar_cursos",
    "coordenador_curso",
    "disciplinas_termo",
    "todos_termos_curso",
    "eletivas_curso",
    "matriz_info",
    "prerequisite_chain",
    "dependents",
    "co_prerequisite",
    "critical_disciplines",
    "recommended_before",
    "trajectory_planning",
    "discipline_docentes",
    "docente_leciona_disciplina",
    "docentes_by_area",
})

META_CAPABILITIES_RESPONSE = """Sim. Tenho acesso a informações da UNIFESP ICT sobre:

- **Disciplinas:** pré-requisitos, ementas, carga horária, docentes e bibliografia
- **Docentes:** contato (email, sala), áreas de pesquisa e disciplinas que lecionam
- **Cursos:** matriz curricular, disciplinas por termo, eletivas
- **Regimentos e normas:** atividades complementares, trancamento, aprovação, FAQs

Pergunte sobre qualquer um desses temas em português."""


_GREETING_WORDS = frozenset({
    "oi", "ola", "olá", "eai", "opa", "alo", "alô", "hey", "hi", "ei",
})
_GREETING_PHRASES = [
    "bom dia", "boa tarde", "boa noite", "e ai", "e aí", "tudo bem",
    "tudo bom", "tudo certo", "como vai", "como voce esta", "como você está",
    "como vc esta", "beleza", "blz", "salve",
]
_THANKS_PHRASES = [
    "obrigado", "obrigada", "obg", "valeu", "vlw", "agradeco", "agradeço",
    "grato", "grata",
]
_FAREWELL_PHRASES = [
    "tchau", "ate logo", "até logo", "ate mais", "até mais", "ate breve",
    "até breve", "adeus", "falou", "flw", "ate a proxima", "até a próxima",
]
_IDENTITY_PHRASES = [
    "quem e voce", "quem é você", "quem e vc", "qual seu nome", "qual o seu nome",
    "voce e um robo", "você é um robô", "voce e uma ia", "você é uma ia",
    "voce e humano", "você é humano", "o que voce e", "o que você é",
    "como voce funciona", "como você funciona", "voce e real", "você é real",
]
_INFO_KEYWORDS = [
    "disciplina", "materia", "matéria", "professor", "docente", "curso",
    "pre-requisito", "pré-requisito", "pre requisito", "prerequisito",
    "ementa", "carga", "matriz", "termo", "credito", "crédito",
    "regimento", "norma", "artigo", "coordenador",
]


def is_conversational(question_lower: str) -> bool:
    """
    True quando a mensagem é conversa social pura (saudação, agradecimento,
    despedida ou pergunta sobre a identidade do assistente) - e não um pedido
    de informação. Conservador: mensagens longas ou com termos informativos
    seguem para os agentes especializados / fallback.
    """
    q = question_lower.strip().strip("?!.,;:").strip()
    if not q:
        return False
    words = q.split()

    if any(p in q for p in _IDENTITY_PHRASES):
        return True

    if q in _GREETING_WORDS:
        return True

    if any(kw in q for kw in _INFO_KEYWORDS):
        return False

    social = _GREETING_PHRASES + _THANKS_PHRASES + _FAREWELL_PHRASES + list(_GREETING_WORDS)
    if len(words) <= 6 and any(
        re.search(rf"\b{re.escape(p)}\b", q) for p in social
    ):
        return True

    return False


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

_MONTAR_GRADE_INFO_EXCLUDE = [
    "quantas horas", "quanto tempo", "o que preciso", "o que e preciso",
    "o que necessito", "requisitos para",
    "integralizar", "integralizacao", "formacao",
]


def is_montar_grade(question_lower: str) -> bool:
    """True se a mensagem pede para montar a grade / planejar a trajetória."""
    q = _strip_accents(question_lower)
    if _any_phrase([_strip_accents(e) for e in _MONTAR_GRADE_INFO_EXCLUDE], q):
        return False
    return any(_strip_accents(p) in q for p in _MONTAR_GRADE_PHRASES)


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
    "extensionista", "extensionistas",
    "integralizar", "integralizacao", "projeto pedagogico", "ppc",
    "pos-bct", "pos bct", "matriz de transicao", "comissao de curso",
    "me formar no", "me formar em", "formar no bct", "formacao no",
    "formacao do", "quantas horas necessito", "quantas horas preciso",
    "nucleo docente", "nde", "ex-officio", "ex officio",
    "atestado", "diploma", "aproveitamento de estudos", "cracha", "crachá",
    "historico escolar", "cancelamento de matricula", "colacao de grau",
    "colacao", "colar grau", "colar o grau", "colo grau", "formatura",
    "concluinte", "concluintes",
    "atualizacao de dados", "certificado de conclusao",
    "rematricula", "matriz horaria", "cancelamento", "dados cadastrais",
    "trancamento de matricula", "prorrogacao", "revisao de prova",
    "ausencias e licencas", "licenca medica", "licencas medicas",
    "peticionamento", "catalogo de disciplinas", "ementario", "oferta de ucs",
    "passe escolar", "trocar de turma", "trocar de turno",
    "troca de turma", "troca de turno",
    "tcc", "trabalho de conclusao", "aluno especial",
    "caltae", "sicad", "gtae", "fapesp", "espaco fisico", "atos normativos",
    "agenda do ict", "agenda do campus", "gestao de contratos", "convenios",
    "desenvolvimento tecnologico", "inovacao tecnologica",
    "sala de estudo", "salas de estudo", "plagio", "similaridade",
    "pergamum", "ficha catalografica", "repositorio institucional",
    "doacao de livros", "emprestimo de livro", "devolucao",
    "dae", "assuntos educacionais", "apoio ao estudante",
    "materiais de aula", "materiais de apoio", "material de apoio",
    "dicas de estudo", "dicas para ingressantes",
    "quadro resumo da graduacao", "quadro geral da graduacao",
    "plano de rematricula", "minicurso", "minicursos",
    "orientacao academica", "relatorio de progresso", "progresso academico",
    "aditamento", "aditamentos", "rescisao",
    "tce", "termo de compromisso", "ecos", "eno",
    "estagio obrigatorio", "estagio nao obrigatorio", "estagiario",
    "relatorio de estagio", "relatorios de estagio", "remat",
    "coordenador de estagio", "coordenadora de estagio",
]


_HOURS_BREAKDOWN_RES = [
    r"\bhoras?\b[^.?!]*\b(?:distribuid|dividid)\w*\b",
    r"\b(?:distribuid|dividid)\w*\b[^.?!]*\bhoras?\b",
    r"\bdistribuicao\s+(?:de\s+|das?\s+)?horas\b",
    r"\bhoras\s+de\s+(?:eletivas?|optativas?|extensao|complementares)\b",
    r"\bhoras\s+(?:de\s+)?(?:atividades\s+complementares|disciplinas\s+obrigatorias|ucs?\s+obrigatorias|obrigatorias)\b",
]


def _is_hours_breakdown(q_sem_acentos: str) -> bool:
    """True se a pergunta pede a QUEBRA das horas do curso (não o total)."""
    return any(re.search(p, q_sem_acentos) for p in _HOURS_BREAKDOWN_RES)


_WEB_SJC_EXCLUDE = [
    "professor", "professora", "docente", "disciplina", "materia", "ementa",
    "pre-requisito", "pre requisito", "prerequisito", "pré-requisito",
    "pre-requisitos", "pre requisitos", "prerequisitos",
    "leciona", "ministra", "carga horaria", "carga horária",
    "tcc i", "tcc ii", "tcc 1", "tcc 2",
    "regimento", "regulamento", "norma", "artigo", "resolucao",
]


def is_web_sjc(question_lower: str) -> bool:
    """True se a pergunta é institucional sobre o campus (coberta pelo site)."""
    q = _strip_accents(question_lower)
    if _any_phrase([_strip_accents(e) for e in _WEB_SJC_EXCLUDE], q):
        return False
    return _any_phrase(_WEB_SJC_PHRASES, q) or _is_hours_breakdown(q)


_COURSE_OVERVIEW_PATTERNS = [
    r"^o\s+que\s+e\s+(?:o\s+curso\s+(?:de\s+)?|o\s+|a\s+)?(.+?)\s*\??$",
    r"^como\s+(?:funciona|e)\s+(?:o\s+curso\s+(?:de\s+)?|o\s+|a\s+)?(.+?)\s*\??$",
    r"^(?:me\s+)?fale\s+(?:mais\s+)?sobre\s+(?:o\s+curso\s+(?:de\s+)?|o\s+|a\s+)?(.+?)\s*\??$",
]


def is_course_overview(question_lower: str, kg) -> bool:
    """
    True quando a pergunta é descritiva ("o que é / como funciona / fale sobre")
    e a entidade resolve para um CURSO no Knowledge Graph - e não para uma
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
            norm = kg._normalize_text(entidade)
            disc_id = kg._index_by_name.get(norm) or kg._index_by_sigla.get(norm)
            if disc_id and kg.graph.nodes[disc_id].get("tipo") == "disciplina":
                return False
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

INTENT_TO_AGENT: Dict[str, str] = {
    "docente_info": "docentes",
    "docente_areas": "docentes",
    "docente_disciplines": "docentes",
    "discipline_docentes": "docentes",
    "docentes_by_area": "docentes",
    "docente_leciona_disciplina": "docentes",
    "disciplinas_termo": "cursos",
    "todos_termos_curso": "cursos",
    "matriz_info": "cursos",
    "eletivas_curso": "cursos",
    "listar_cursos": "cursos",
    "coordenador_curso": "cursos",
    "prerequisite_chain": "disciplinas",
    "recommended_before": "disciplinas",
    "dependents": "disciplinas",
    "co_prerequisite": "disciplinas",
    "critical_disciplines": "disciplinas",
    "ementa_disciplina": "disciplinas",
    "trajectory_planning": "disciplinas",
    "artigos_sobre": "regimentos",
    "faqs": "regimentos",
}

REGIMENTO_FORCE_KEYWORDS = [
    "regimento", "regulamento", "norma", "artigo", "resolucao",
    "evacuacao", "incendio", "seguranca", "faq", "perguntas frequentes",
    "atividade complementar", "atividades complementares",
    "trancamento", "trancar", "aprovacao", "reprovacao",
    "indeferimento", "indeferida", "indeferido", "deferimento",
    "preenchimento de vagas", "prioridade na matricula",
    "criterios de matricula", "criterios de prioridade",
    "coeficiente de rendimento", "cr",
    "vagas em uc", "vagas na uc", "vagas de uma uc",
    "matricula em uc", "matricula em ucs",
    "inscricao em uc", "inscricao na uc", "inscricao em ucs",
    "inscricao em duas uc", "inscricao em duas ucs",
]


def is_regimento_domain(question_lower: str) -> bool:
    q = _strip_accents(question_lower)
    return _any_phrase([_strip_accents(k) for k in REGIMENTO_FORCE_KEYWORDS], q)

CURSOS_SEQ_KEYWORDS = [
    "sequencial", "sequenciais", "certificado",
    "fundamentos de ciência", "fundamentos de ciencia",
    "métodos estatísticos", "metodos estatisticos",
    "economia e mercados", "química aplicada", "quimica aplicada",
    "desenvolvimento de games", "jogos digitais",
]

DISCIPLINE_DOCENTES_PHRASES = [
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
    "sobre o professor",
    "sobre a professora",
    "sobre o docente",
    "sobre a docente",
    "quem é o professor",
    "quem é a professora",
    "quem e o professor",
    "quem e a professora",
    "professor responsavel",
    "professor responsável",
    "professora responsavel",
    "professora responsável",
    "docente responsavel",
    "docente responsável",
    "responsavel pela disciplina",
    "responsável pela disciplina",
    "responsavel pela materia",
    "responsável pela matéria",
    "responsavel por",
    "responsável por",
    "costuma lecionar",
    "costuma ensinar",
    "disciplinas que ele",
    "disciplinas que ela",
    "disciplinas lecionadas por",
    "disciplinas ministradas por",
    "disciplinas do professor",
    "disciplinas da professora",
]

PREREQUISITE_PHRASES = [
    "pre-requisito", "pre requisito", "prerequisito",
    "pré-requisito", "pré requisito",
    "antes de cursar", "antes de fazer",
    "preciso cursar", "preciso de",
    "depende de", "dependem de",
]

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

    Fonte única de verdade para os overrides - usada tanto por route_intent
    (caminho sem embeddings) quanto pelo pipeline (por cima do roteamento por
    embeddings, substituindo correções hardcoded pontuais).

    Ordem de prioridade:
    1. Docentes (frases como "quais docentes dão X", "sobre a professora Y")
    2. Pré-requisitos → disciplinas
    3. Info/ementa de disciplina → disciplinas
       (quando vindo do embedding, só corrige a partir de docentes - não
        sobrescreve uma escolha explícita de cursos/regimentos)
    4. Regimentos (keywords institucionais)
    5. Cursos sequenciais
    """
    if _any_phrase(DISCIPLINE_DOCENTES_PHRASES, question_lower):
        return "docentes"

    if _any_phrase(PREREQUISITE_PHRASES, question_lower):
        return "disciplinas"

    if current_agent in ("", "docentes", "disciplinas") and _any_phrase(
        DISCIPLINE_INFO_PHRASES, question_lower
    ):
        return "disciplinas"

    if _any_phrase(REGIMENTO_FORCE_KEYWORDS, question_lower):
        return "regimentos"

    if _any_phrase(CURSOS_SEQ_KEYWORDS, question_lower):
        return "cursos"

    return None


LLM_ROUTE_AGENTS: frozenset = frozenset({
    "disciplinas", "docentes", "cursos", "regimentos",
    "conversa", "montar_grade", "noticias", "web_sjc",
})

AGENTIC_INTENTS: frozenset = frozenset({
    "ac_auditoria", "ac_checklist", "progresso",
    "matricula_check", "risco_reprovacao", "trilha", "cr_consulta",
    "oferta_check", "requisitos_curso",
})

_LLM_ROUTE_INTENTS: frozenset = frozenset(
    {
        "docente_info", "docente_areas", "docente_disciplines",
        "discipline_docentes", "docentes_by_area", "docente_leciona_disciplina",
        "disciplinas_termo", "todos_termos_curso", "matriz_info",
        "eletivas_curso", "listar_cursos", "coordenador_curso",
        "prerequisite_chain", "dependents", "co_prerequisite",
        "critical_disciplines", "ementa_disciplina", "trajectory_planning",
        "recommended_before",
        "artigos_sobre", "faqs",
        "conversa", "noticias", "web_sjc", "plan_curriculum", "unknown",
    }
    | AGENTIC_INTENTS
)

_LLM_ROUTE_TEMPLATE = """Voce e o roteador de um assistente academico da UNIFESP ICT (campus Sao Jose dos Campos). Escolha o agente mais adequado para responder a pergunta do aluno.

AGENTES DISPONIVEIS:
- disciplinas: ementas, pre-requisitos, carga horaria e descricao de disciplinas/materias
- docentes: professores - contato, sala, areas de pesquisa, quem leciona qual disciplina
- cursos: matrizes curriculares, disciplinas por termo, eletivas, coordenacao de curso
- regimentos: normas, regimentos, regulamentos, artigos, FAQs institucionais
- conversa: saudacoes, agradecimentos, small talk sem pedido de informacao
- montar_grade: pedido explicito de montar/planejar a grade ou trajetoria do aluno
- noticias: noticias, novidades e eventos da UNIFESP
- web_sjc: paginas do site do campus - ingresso, secretaria, biblioteca, pos-graduacao, servicos, orgaos, apresentacao dos cursos

INTENTS DE ACAO (use um destes como intent quando o aluno quer que o sistema
aplique as regras ao caso DELE, independente do modo de falar):
- ac_auditoria: menciona horas de atividades e quer saber quanto conta como Atividade Complementar, ou se uma atividade especifica vale horas
- ac_checklist: quer saber se esta pronto ou o que precisa para enviar/peticionar as Atividades Complementares
- progresso: quer saber o que falta para se formar, concluir ou integralizar o curso, ou pede auditoria da situacao dele
- matricula_check: quer saber se conseguira se matricular/inscrever em UCs especificas ou se a inscricao sera deferida
- risco_reprovacao: pergunta o que acontece ou o que atrasa se reprovar/nao passar em uma disciplina
- trilha: quer recomendacao de disciplinas ou caminho de estudos para um objetivo, carreira ou area de interesse
- cr_consulta: pergunta sobre o proprio CR (coeficiente de rendimento) ou quer simular como uma nota afetaria o CR
- oferta_check: quer saber se/quando uma disciplina sera ofertada, se vai ter no proximo semestre ou em qual semestre ela abre
- requisitos_curso: pergunta quantas horas ou quais requisitos (fixas, eletivas, AC, estagio, TCC) sao exigidos para se formar/integralizar um curso

HISTORICO RECENTE DA CONVERSA (pode estar vazio):
{history}

PERGUNTA DO ALUNO: {question}

Responda APENAS com um JSON valido (sem markdown, sem comentarios) no formato:
{{"agente": "<disciplinas|docentes|cursos|regimentos|conversa|montar_grade|noticias|web_sjc>", "intent": "<rotulo curto, ex.: ementa_disciplina, prerequisite_chain, discipline_docentes, coordenador_curso, matriz_info, faqs, ac_auditoria, progresso, risco_reprovacao, trilha, conversa, unknown>", "entidades": {{"disciplina": "<nome da disciplina citada ou null>", "curso": "<nome ou sigla do curso citado ou null>", "docente": "<nome do docente citado ou null>"}}}}

JSON:"""


def _extract_json_block(raw: str) -> Optional[dict]:
    """Extrai o primeiro objeto JSON do texto (tolerante a cercas de código)."""
    if not raw:
        return None
    text = str(raw).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _ground_entity(kg, valor, tipos) -> Optional[str]:
    """
    Aterra uma entidade no KG: retorna o nome canônico do nó ou None se a
    entidade não resolve (rejeita o que o LLM inventou).
    """
    if kg is None or valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() in ("null", "none", "n/a"):
        return None
    for tipo in tipos:
        try:
            node_id = kg._find_node(texto, tipo)
        except Exception:
            node_id = None
        if node_id:
            try:
                nome = kg.graph.nodes[node_id].get("nome")
            except Exception:
                nome = None
            return nome or texto
    return None


_ROUTER_LLM_NUM_PREDICT = 150
_router_llm_singleton = {"key": None, "llm": None}


def _get_router_llm():
    """Instância própria (lazy, cacheada) do modelo dedicado de roteamento."""
    model = os.getenv("FESPAI_ROUTER_MODEL", "").strip()
    if not model:
        return None
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip() or None
    key = (model, base_url)
    if _router_llm_singleton["key"] == key:
        return _router_llm_singleton["llm"]
    try:
        from langchain_ollama import OllamaLLM

        kwargs = dict(
            model=model,
            keep_alive=3600,
            num_predict=_ROUTER_LLM_NUM_PREDICT,
            temperature=0,
            timeout=30,
        )
        if base_url:
            kwargs["base_url"] = base_url
        try:
            llm = OllamaLLM(reasoning=False, **kwargs)
        except Exception:
            llm = OllamaLLM(**kwargs)
    except Exception:
        llm = None
    _router_llm_singleton["key"] = key
    _router_llm_singleton["llm"] = llm
    return llm


_ROUTE_CACHE_MAX = 500
_route_cache: "OrderedDict[str, dict]" = OrderedDict()


def _route_cache_key(question: str) -> str:
    """Normaliza a pergunta para chave de cache."""
    q = _strip_accents((question or "").lower())
    return re.sub(r"\s+", " ", q).strip()


def clear_route_cache() -> None:
    """Limpa o cache de roteamento (testes / troca de KG)."""
    _route_cache.clear()


def _route_cache_get(key: str) -> Optional[dict]:
    cached = _route_cache.get(key)
    if cached is None:
        return None
    _route_cache.move_to_end(key)
    return {
        "agente": cached["agente"],
        "intent": cached["intent"],
        "entidades": dict(cached["entidades"]),
    }


def _route_cache_put(key: str, decision: dict) -> None:
    if not key:
        return
    _route_cache[key] = {
        "agente": decision["agente"],
        "intent": decision["intent"],
        "entidades": dict(decision["entidades"]),
    }
    _route_cache.move_to_end(key)
    while len(_route_cache) > _ROUTE_CACHE_MAX:
        _route_cache.popitem(last=False)


def llm_route(
    question: str,
    history: str,
    kg,
    llm,
    telemetry_incr: Optional[Callable[[str], None]] = None,
) -> Optional[dict]:
    """
    Roteador LLM unificado: UMA chamada decide agente + intent + entidades.

    Retorna {"agente": <um dos 8>, "intent": <str>, "entidades": {...}} com as
    entidades aterradas no KG (não-resolvidas são descartadas), ou None quando
    o LLM está indisponível / o JSON é inválido / o agente não existe - nesses
    casos o chamador usa o embedding router como fallback.

    Latência: (1) cache LRU por pergunta normalizada evita chamadas repetidas;
    (2) se FESPAI_ROUTER_MODEL estiver setada, usa um modelo pequeno dedicado
    em vez do LLM de geração.
    """
    if llm is None:
        return None

    cache_key = _route_cache_key(question)
    cached = _route_cache_get(cache_key)
    if cached is not None:
        if telemetry_incr:
            telemetry_incr("llm_route_cache_hit")
        return cached

    route_llm = _get_router_llm() or llm
    prompt = _LLM_ROUTE_TEMPLATE.format(
        history=(history or "").strip() or "(vazio)",
        question=question,
    )
    try:
        raw = route_llm.invoke(prompt)
    except Exception:
        return None
    raw = getattr(raw, "content", raw)
    data = _extract_json_block(raw)
    if not data:
        return None

    agente = str(data.get("agente", "")).strip().lower()
    if agente not in LLM_ROUTE_AGENTS:
        return None

    intent = str(data.get("intent", "") or "").strip().lower()
    if intent not in _LLM_ROUTE_INTENTS:
        intent = ""

    entidades_raw = data.get("entidades") or {}
    if not isinstance(entidades_raw, dict):
        entidades_raw = {}
    entidades: Dict[str, str] = {}
    grounded = _ground_entity(kg, entidades_raw.get("disciplina"), ("disciplina",))
    if grounded:
        entidades["disciplina"] = grounded
    grounded = _ground_entity(kg, entidades_raw.get("curso"), ("curso", "matriz_curricular"))
    if grounded:
        entidades["curso"] = grounded
    grounded = _ground_entity(kg, entidades_raw.get("docente"), ("docente",))
    if grounded:
        entidades["docente"] = grounded

    decision = {"agente": agente, "intent": intent, "entidades": entidades}
    _route_cache_put(cache_key, decision)
    return decision


def term_from_llm_route(routed: dict) -> str:
    """Escolhe o termo (entidade aterrada) relevante para o agente decidido."""
    if not routed:
        return ""
    entidades = routed.get("entidades") or {}
    agente = routed.get("agente", "")
    if agente == "disciplinas":
        return entidades.get("disciplina", "")
    if agente == "docentes":
        return entidades.get("docente", "") or entidades.get("disciplina", "")
    if agente == "cursos":
        return entidades.get("curso", "")
    return ""


def route_intent(intent: str, question_lower: str) -> str:
    """
    Determina qual agente deve tratar a pergunta.
    Aplica overrides por frase antes de consultar o mapa de intents.
    """
    override = phrase_override(question_lower)
    if override:
        return override

    if intent in INTENT_TO_AGENT:
        return INTENT_TO_AGENT[intent]

    return "fallback"
