import re
from typing import Optional, List, Dict, Tuple
from .knowledge_graph import KnowledgeGraph
from .intent_classifier import IntentClassifier, ClassificationResult

class GraphRAGEngine:
    """Metodologia híbrida GraphRAG + RAG"""

    def __init__(self, knowledge_graph: KnowledgeGraph, embeddings_model=None, llm=None):
        self.kg = knowledge_graph

        self.intent_classifier = IntentClassifier(embeddings_model, llm=llm)
        self._use_semantic_classification = embeddings_model is not None

        self.graph_patterns = {
            'recommended_before': [
                r'(?:o\s+que\s+)?(?:[eé]\s+)?(?:bom|legal|[uú]til|recomendad[oa]s?|indicad[oa]s?)\s+(?:fazer|cursar|estudar|ter\s+feito)\s+antes\s+de\s+(?:fazer\s+|cursar\s+)?(.+?)(?:\?|$)',
                r'o\s+que\s+ajuda(?:ria)?\s+(?:a\s+)?(?:fazer|cursar|estudar)?\s*antes\s+de\s+(?:fazer\s+|cursar\s+)?(.+?)(?:\?|$)',
                r'vale\s+a\s+pena\s+(?:fazer|cursar)\s+(?:o\s+qu[eê]\s+)?antes\s+de\s+(.+?)(?:\?|$)',
                r'(?:disciplinas?\s+)?recomendad[oa]s?\s+antes\s+de\s+(.+?)(?:\?|$)',
            ],
            'prerequisite_chain': [
                r'(?:quais?|todos?)\s+(?:s[aã]o\s+)?(?:os?\s+)?pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
                r'(?:o\s+que|quais?\s+disciplinas?)\s+(?:preciso|precisa|devo|deve)\s+(?:fazer|cursar|ter)\s+(?:antes\s+de|para\s+fazer|para\s+cursar)\s+(.+?)(?:\?|$)',
                r'cadeia\s+(?:de\s+)?pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
                r'pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
                r'(?:preciso|precisa)\s+(?:ter\s+feito|ter\s+cursado|cursar|fazer)\s+(?:o\s+qu[eê]\s+)?(?:antes\s+(?:de|para)\s+(?:cursar|fazer)\s+)?(.+?)(?:\?|$)',
            ],
            'dependents': [
                r'(?:quais?\s+)?disciplinas?\s+(?:que\s+)?depend(?:e|em)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?disciplinas?\s+(?:que\s+)?(?:usam?|precisam?|requerem?|exigem?)\s+(.+?)\s+como\s+pr[eé][-\s]?requisito(?:\?|$)',
                r'(?:para\s+)?(?:o\s+)?que\s+(.+?)\s+[eé]\s+pr[eé][-\s]?requisito(?:\?|$)',
                r'(?:o\s+que\s+)?(.+?)\s+desbloqueia(?:\?|$)',
                r'(?:o\s+que\s+)?(.+?)\s+[eé]\s+pr[eé][-\s]?requisito\s+(?:de\s+qu[eê]|para\s+qu[eê]|de\s+qu(?:a|ai)s?)(?:\?|$)',
            ],
            'docente_disciplines': [
                r'(?:quais?\s+)?(?:disciplinas?|mat[eé]rias?)\s+(?:que\s+)?(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)\s+(?:leciona|ensina|ministra|d[aá])(?:\?|$)',
                r'(?:o\s+que|quais?)\s+(?:o\s+|a\s+)?(.+?)\s+(?:leciona|ensina|ministra|d[aá])(?:\?|$)',
            ],
            'discipline_docentes': [
                r'(?:professor(?:es|a)?|docentes?)\s+respons[aá]ve(?:l|is)\s+(?:por|pel[ao])\s+(?:a\s+|o\s+)?(?:disciplina\s+(?:de\s+)?|mat[eé]ria\s+(?:de\s+)?)?(.+?)(?:\?|$)',
                r'quem\s+(?:[eé]\s+)?(?:o\s+|a\s+)?respons[aá]vel\s+(?:por|pel[ao])\s+(?:a\s+|o\s+)?(?:disciplina\s+(?:de\s+)?|mat[eé]ria\s+(?:de\s+)?)?(.+?)(?:\?|$)',
                r'quem\s+(?:leciona|ensina|ministra|d[aá])\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:de|da|do|que\s+d[aã]o)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:que\s+)?(?:lecionam?|ensinam?|ministram?|d[aã]o)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            ],
            'docente_leciona_disciplina': [
                r'(?:o\s+|a\s+)?(?:professor(?:a)?|docente)\s+(.+?)\s+leciona\s+(.+?)(?:\?|$)',
                r'(?:o\s+|a\s+)?([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)\s+(?:leciona|d[aá]|ensina|ministra)\s+(.+?)(?:\?|$)',
            ],
            'artigos_sobre': [
                r'(?:quais?\s+)?artigos?\s+(?:sobre|que\s+(?:falam?|tratam?|mencionam?))\s+(.+?)(?:\?|$)',
                r'(?:o\s+que|quais?)\s+(?:os?\s+)?(?:artigos?|regras?|normas?)\s+(?:dizem?|falam?)\s+sobre\s+(.+?)(?:\?|$)',
            ],
            'faqs': [
                r'(?:perguntas?\s+)?(?:frequentes?|comuns?)\s+sobre\s+(.+?)(?:\?|$)',
                r'(?:d[uú]vidas?\s+)?(?:sobre|comuns?\s+sobre)\s+(.+?)(?:\?|$)',
            ],
            'docentes_by_area': [
                r'(?:quais?\s+)?(?:professore?s?|docentes?)\s+(?:que\s+)?(?:trabalham?|pesquisam?|s[aã]o\s+especialistas?)\s+(?:com|em)\s+(.+?)(?:\?|$)',
                r'(?:quem\s+)?(?:trabalha|pesquisa|[eé]\s+especialista)\s+(?:com|em)\s+(.+?)(?:\?|$)',
                r'especialistas?\s+(?:em|de)\s+(.+?)(?:\?|$)',
            ],
            'docente_areas': [
                r'(?:quais?\s+)?(?:as?\s+)?[aá]reas?\s+(?:de\s+)?(?:especializa[çc][aã]o|pesquisa|atua[çc][aã]o)\s+(?:de|do|da)\s+(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'(?:em\s+que|quais?\s+[aá]reas?)\s+(?:o\s+|a\s+)?(.+?)\s+(?:pesquisa|trabalha|atua|[eé]\s+especialista)(?:\?|$)',
                r'(?:qual|quais?)\s+(?:[eé]\s+)?(?:a\s+)?[aá]reas?\s+(?:de|do|da)\s+(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'[aá]reas?\s+(?:de|do|da)\s+(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'(?:quero\s+fazer\s+(?:uma?\s+)?(?:ic|inicia[çc][aã]o\s+cient[ií]fica)\s+com\s+(?:o\s+|a\s+)?(.+?))[\.,]\s*(?:qual|pode\s+me\s+dizer)\s+(?:a\s+)?[aá]rea',
                r'(?:pode\s+me\s+dizer|me\s+diz(?:er)?|qual\s+[eé])\s+(?:a\s+)?[aá]rea\s+(?:de|do|da)\s+(?:o\s+|a\s+)?(.+?)(?:\?|$)',
                r'(?:pode\s+me\s+dizer|me\s+diz(?:er)?)\s+(?:a\s+)?[aá]rea\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
            ],
            'docente_info': [
                r'(?:qual|quais?)\s+(?:[oé]\s+)?(?:o\s+)?e[-\s]?mail\s+(?:de|do|da)\s+(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'(?:qual|onde)\s+(?:[eé]\s+)?(?:a\s+)?sala\s+(?:de|do|da)\s+(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'onde\s+fica\s+(?:a\s+sala\s+)?(?:de|do|da)\s+(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'(?:como\s+)?(?:entro\s+em\s+)?contato\s+(?:com\s+)?(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
                r'(?:informa[çc][oõ]es?|dados?)\s+(?:de|do|da|sobre)\s+(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)(?:\?|$)',
            ],
            'disciplinas_termo': [
                r'(?:quais?\s+)?disciplinas?\s+(?:do|de)\s+(?:termo|semestre|per[ií]odo)\s+(\d+)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:o\s+que\s+)?(?:tem\s+)?(?:no\s+)?(?:termo|semestre|per[ií]odo)\s+(\d+)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?disciplinas?\s+(?:do|de)\s+(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|s[eé]tim[oa]|oitav[oa]|non[oa]|d[eé]cim[oa])\s+(?:termo|semestre|per[ií]odo)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:o\s+que\s+)?(?:tem\s+)?(?:no\s+)?(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|s[eé]tim[oa]|oitav[oa]|non[oa]|d[eé]cim[oa])\s+(?:termo|semestre|per[ií]odo)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
            ],
            'eletivas_curso': [
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:as?\s+)?eletivas?\s+do\s+grupo\s+\d+\s+(?:de|do|da|para)\s+(.+?)(?:\?|$)',
                r'(?:como\s+)?funcionam?\s+(?:as?\s+)?(?:disciplinas?\s+)?eletivas?\s+(?:de|do|da|no|na)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:as?\s+)?eletivas?\s+(?:de|do|da|para|d[oe])\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?disciplinas?\s+eletivas?\s+(?:de|do|da|para)\s+(.+?)(?:\?|$)',
                r'eletivas?\s+(?:dispon[ií]veis?\s+)?(?:para|no|na|do|da|de)\s+(.+?)(?:\?|$)',
                r'(?:liste|mostre|quero\s+ver)\s+(?:as?\s+)?eletivas?\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
            ],
            'trajectory_planning': [
                r'(?:j[aá]\s+)?(?:cursei|fiz|conclui|conclu[ií])\s+(.+?)[,:]\s+(?:como\s+)?(?:chego|chegar|fica)\s+(?:em\s+)?([^.!?]+?)(?:[.!?]|$)',
                r'(?:j[aá]\s+)?(?:fiz|conclui|conclu[ií])\s+(.+?)[,.]?\s+(?:como\s+fica|o\s+que\s+falta)\s*\??',
                r'quero\s+chegar\s+em\s+([^,.!?]+?),\s+(?:j[aá]\s+)?(?:fiz|cursei|conclui|conclu[ií])\s+([^.!?]+?)(?:[.!?]|$)',
                r'quero\s+chegar\s+em\s+([^,.!?]+?)(?:[,.!?]|$)',
                r'caminho\s+(?:m[ií]nimo\s+)?para\s+(?:chegar\s+(?:em|at[eé])\s+)?([^.!?]+?)(?:[.!?]|$)',
                r'como\s+cheg(?:o|ar)\s+(?:em|at[eé])\s+([^.!?]+?)(?:[.!?]|$)',
                r'sequência\s+(?:de\s+disciplinas?\s+)?para\s+(?:cursar\s+)?([^.!?]+?)(?:[.!?]|$)',
                r'planejamento\s+para\s+cursar\s+([^.!?]+?)(?:[.!?]|$)',
                r'(?:chegar?\s+(?:em|at[eé])|at[eé])\s+([^.!?]+?)(?:[.!?]|$)',
            ],
            'matriz_info': [
                r'(?:qual|como\s+[eé])\s+(?:a\s+)?matriz\s+(?:curricular\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:qual|como\s+[eé])\s+(?:a\s+)?estrutura\s+(?:do\s+curso\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'estrutura\s+(?:curricular\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'quantos?\s+termos?\s+(?:tem|possui|dura)\s+(?:o\s+)?(?:curso\s+)?(?:de\s+)?(.+?)(?:\?|$)',
                r'dura[çc][aã]o\s+(?:do\s+curso\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'carga\s+hor[aá]ria\s+(?:total\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:quantas?\s+)?horas?\s+(?:tem|precisa|possui)\s+(?:o\s+)?(?:curso\s+)?(?:de\s+)?(.+?)(?:\?|$)',
                r'(?:me\s+)?fale\s+(?:sobre\s+)?(?:a\s+)?(?:matriz\s+)?(?:do|da|de)\s+(.+?)(?:\?|$)',
                r'(?:sobre\s+)?(?:a\s+)?matriz\s+(?:do|da|de)\s+(.+?)(?:\?|$)',
            ],
            'todos_termos_curso': [
                r'(?:me\s+fale\s+|fale\s+)?(?:sobre\s+)?(?:as\s+)?disciplinas?\s+(?:de\s+)?(?:todos?\s+)?(?:os\s+)?termos?\s+(?:da\s+)?(?:matriz\s+)?(?:curricular\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:as\s+)?disciplinas?\s+(?:dos?\s+)?(?:todos?\s+)?(?:os\s+)?termos?\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:todas?\s+)?(?:as\s+)?disciplinas?\s+(?:da\s+)?(?:matriz\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:lista|listar|mostre|ver)\s+(?:todas?\s+)?(?:as\s+)?disciplinas?\s+(?:por\s+termo\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'grade\s+(?:curricular\s+)?(?:completa\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
            ],
            'coordenador_curso': [
                r'quem\s+(?:[eé]\s+)?(?:o\s+|a\s+)?coordena(?:dor(?:a)?)?(?:\s+(?:de|do|da))?\s+(.+?)(?:\?|$)',
                r'(?:qual|quem)\s+(?:[eé]\s+)?(?:o\s+|a\s+)?coordena(?:dor(?:a)?|[çc][aã]o)\s+(?:de|do|da|d[oe])\s+(.+?)(?:\?|$)',
                r'coordena(?:dor(?:a)?|[çc][aã]o)\s+(?:de|do|da|d[oe])\s+(.+?)(?:\?|$)',
                r'(?:qual|quem)\s+(?:[eé]\s+)?(?:o\s+|a\s+)?vice[-\s]?coordena(?:dor(?:a)?)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
            ],
            'listar_cursos': [
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:os?\s+)?cursos?\s+(?:que\s+)?(?:a\s+)?(?:unifesp|ict|unifesp\s+ict)\s+(?:oferece|tem|possui)(?:\?|$)',
                r'(?:quais?\s+)?cursos?\s+(?:tem|oferece|possui)\s+(?:a\s+|o\s+)?(?:unifesp|ict)(?:\?|$)',
                r'(?:liste|mostre|quero\s+ver)\s+(?:os?\s+)?cursos?\s+(?:do|da|de)\s+(?:unifesp|ict)(?:\?|$)',
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:os?\s+)?cursos?\s+(?:dispon[ií]veis?|oferecidos?)(?:\?|$)',
                r'cursos?\s+(?:de\s+)?gradua[çc][aã]o\s+(?:do|da|no|na)\s+(?:unifesp|ict)(?:\?|$)',
            ],
        }

    def set_llm(self, llm) -> None:
        """Injeta o LLM após a construção (chamado em rag.py após inicializar o LLM)."""
        self.intent_classifier.set_llm(llm)

    def initialize_classifier(self):
        """Inicializa o classificador de intenção com embeddings."""
        if self._use_semantic_classification:
            self.intent_classifier.initialize()
    
    def should_use_graph(self, question: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Determina se a pergunta deve usar GraphRAG.
        Retorna: (usar_graph, tipo_query, termo_extraido)
        Para disciplinas_termo, retorna termo como "termo:curso" (ex: "5:bcc")
        
        Usa classificação semântica (embeddings) quando disponível,
        com fallback para regex.
        """
        if self._use_semantic_classification and self.intent_classifier._initialized:
            result = self.intent_classifier.classify(question)

            if result.intent != 'unknown' and result.confidence >= 0.45:
                intent, term = self._fix_docente_direction(
                    question, result.intent, result.term
                )
                termo = self._post_process_term(question, intent, term)
                termo = self._ground_discipline_term(question, intent, termo)
                termo = self._ground_curso_term(question, intent, termo)
                termo = self._ground_docente_term(question, intent, termo)
                return True, intent, termo

        use, intent, termo = self._regex_fallback(question)
        if use and intent and termo:
            intent, termo = self._fix_docente_direction(question, intent, termo)
            termo = self._ground_discipline_term(question, intent, termo)
            termo = self._ground_curso_term(question, intent, termo)
            termo = self._ground_docente_term(question, intent, termo)
        return use, intent, termo

    _DOCENTE_DIRECTION_INTENTS = {
        'docente_disciplines', 'discipline_docentes', 'disciplina_docentes',
        'docente_areas', 'docentes_by_area',
    }
    _DISCIPLINE_SIDE_INTENTS = {
        'docente_disciplines', 'discipline_docentes', 'disciplina_docentes',
    }

    _AREA_HINT_RE = re.compile(
        r'\b(trabalh\w*|pesquis\w*|atua\w*|[aá]reas?|especialist\w*|'
        r'especializa\w*)\b',
        re.IGNORECASE,
    )

    def _mentioned_in_question(self, question: str, termo: str) -> bool:
        """True se o termo (normalizado) aparece literalmente na pergunta."""
        t = self.kg._normalize_text(termo)
        return bool(t) and f" {t} " in f" {self.kg._normalize_text(question)} "

    def _resolve_docente(self, termo: str) -> Optional[str]:
        """
        ID do docente para o termo, com guarda de sobreposição de palavras:
        o substring-match do KG é frouxo demais para termos curtos/lixo
        (ex.: 'o q' ⊂ 'eduardo quinteiro') - exige ao menos uma palavra do
        termo igual a uma palavra do nome.
        """
        doc_id = self.kg._find_docente_id(termo)
        if not doc_id:
            return None
        termo_words = set(self.kg._normalize_text(termo).split())
        nome_words = set(self.kg._normalize_text(doc_id.replace("DOC:", "")).split())
        return doc_id if termo_words & nome_words else None

    def _docente_intent_for_question(self, question: str, intent: str) -> str:
        """
        Intent do lado do docente: preserva o original quando já é de docente;
        senão decide áreas × disciplinas pelas pistas lexicais da pergunta
        ("trabalha com/pesquisa/área" → áreas; "leciona/ensina" → disciplinas).
        """
        if intent in ('docente_areas', 'docente_info'):
            return intent
        if self._AREA_HINT_RE.search(question):
            return 'docente_areas'
        return 'docente_disciplines'

    def _find_docente_in_text(self, text: str) -> str:
        """
        Retorna o nome do docente do KG citado no texto: nome completo (match
        mais longo) ou, na falta, um nome/sobrenome que identifique UM único
        docente (ex.: "a lilian" → "Lilian Berton").
        """
        text_norm = f" {self.kg._normalize_text(text)} "
        text_words = set(text_norm.split())
        best_nome, best_len = "", 0
        partial: Dict[str, set] = {}
        for _, data in self.kg.graph.nodes(data=True):
            if data.get("tipo") != "docente":
                continue
            nome = data.get("nome", "")
            nome_norm = self.kg._normalize_text(nome)
            if not nome_norm:
                continue
            if f" {nome_norm} " in text_norm:
                if len(nome_norm) > best_len:
                    best_nome, best_len = nome, len(nome_norm)
                continue
            for w in nome_norm.split():
                if len(w) >= 4 and w in text_words:
                    partial.setdefault(w, set()).add(nome)
        if best_nome:
            return best_nome
        unicos = {next(iter(nomes)) for nomes in partial.values() if len(nomes) == 1}
        if len(unicos) == 1:
            return unicos.pop()
        return ""

    def _fix_docente_direction(
        self, question: str, intent: str, termo: str
    ) -> Tuple[str, str]:
        """Corrige direção docente↔disciplina↔área (e termo alucinado) via KG."""
        if intent not in self._DOCENTE_DIRECTION_INTENTS:
            return intent, termo
        try:
            if termo:
                if intent in self._DISCIPLINE_SIDE_INTENTS and \
                        self._mentioned_in_question(question, termo) and \
                        self.kg._find_node(termo, 'disciplina'):
                    return 'discipline_docentes', termo
                if self.kg.get_docentes_by_area(termo):
                    return 'docentes_by_area', termo
                if self._resolve_docente(termo):
                    return self._docente_intent_for_question(question, intent), termo
            grounded = self._find_docente_in_text(question)
            if grounded:
                from .telemetry import incr
                incr("grounding_docente")
                return self._docente_intent_for_question(question, intent), grounded
        except Exception:
            pass
        if intent == 'disciplina_docentes':
            intent = 'discipline_docentes'
        return intent, termo

    _CURSO_TERM_INTENTS = {
        'eletivas_curso', 'matriz_info', 'coordenador_curso', 'todos_termos_curso',
    }

    def _ground_curso_term(self, question: str, intent: str, termo: str) -> str:
        """
        Garante que o termo de intents de curso resolve no KG; se a extração
        capturou lixo (ex.: "algumas dessas eletivas"), procura um curso citado
        literalmente na pergunta.
        """
        if intent not in self._CURSO_TERM_INTENTS or not termo:
            return termo
        if self.kg._find_node(termo.strip(), "curso") or \
           self.kg._find_node(termo.strip(), "matriz_curricular"):
            return termo
        grounded = self._find_curso_in_text(question)
        if grounded:
            from .telemetry import incr
            incr("grounding_curso")
            return grounded
        return termo

    def _find_curso_in_text(self, text: str) -> str:
        """Retorna o nome do curso/matriz do KG citado no texto (match mais longo)."""
        text_norm = f" {self.kg._normalize_text(text)} "
        best_nome, best_len = "", 0
        for _, data in self.kg.graph.nodes(data=True):
            if data.get("tipo") not in ("curso", "matriz_curricular"):
                continue
            for chave in (data.get("nome", ""), data.get("sigla") or ""):
                chave_norm = self.kg._normalize_text(chave)
                if chave_norm and len(chave_norm) > best_len and f" {chave_norm} " in text_norm:
                    best_nome, best_len = data.get("nome", ""), len(chave_norm)
        return best_nome

    _DISCIPLINE_TERM_INTENTS = {
        'prerequisite_chain', 'dependents', 'discipline_docentes',
        'ementa_disciplina', 'co_prerequisite', 'trajectory_planning',
        'recommended_before',
    }

    def _ground_discipline_term(self, question: str, intent: str, termo: str) -> str:
        """
        Garante que o termo extraído resolve para uma disciplina do KG.
        A extração por regex/stopwords pode capturar lixo (ex.: "feito
        disciplinas total"); nesse caso, procura uma disciplina do KG citada
        literalmente na pergunta e usa o match mais longo.
        """
        if intent not in self._DISCIPLINE_TERM_INTENTS or not termo:
            return termo
        completed = ""
        target = termo
        if intent == 'trajectory_planning' and ':' in termo:
            completed, target = termo.rsplit(':', 1)
            if not target.strip():
                return termo
        if self.kg._find_node(target.strip(), "disciplina"):
            return termo
        grounded = self._find_discipline_in_text(question)
        if not grounded:
            return termo
        from .telemetry import incr
        incr("grounding_disciplina")
        return f"{completed}:{grounded}" if completed else grounded

    _DOCENTE_TERM_INTENTS = {
        'docente_areas', 'docente_info', 'docente_disciplines',
    }

    def _ground_docente_term(self, question: str, intent: str, termo: str) -> str:
        """
        Garante que o termo de intents de docente resolve no KG; se a extração
        capturou lixo ou um nome que não resolve (ex.: "a lilian"), procura um
        docente citado na pergunta e canonicaliza ("Lilian Berton").
        """
        if intent not in self._DOCENTE_TERM_INTENTS or not termo:
            return termo
        if self._resolve_docente(termo):
            return termo
        grounded = self._find_docente_in_text(question)
        if grounded:
            from .telemetry import incr
            incr("grounding_docente")
            return grounded
        return termo

    def _find_discipline_in_text(self, text: str) -> str:
        """Retorna o nome da disciplina do KG citada no texto (match mais longo)."""
        text_norm = f" {self.kg._normalize_text(text)} "
        best_nome, best_len = "", 0
        for _, data in self.kg.graph.nodes(data=True):
            if data.get("tipo") != "disciplina":
                continue
            for chave in (data.get("nome", ""), data.get("sigla") or ""):
                chave_norm = self.kg._normalize_text(chave)
                if chave_norm and len(chave_norm) > best_len and f" {chave_norm} " in text_norm:
                    best_nome, best_len = data.get("nome", ""), len(chave_norm)
        return best_nome
    
    def _post_process_term(self, question: str, intent: str, term: str) -> str:
        """Pós-processamento do termo extraído para casos especiais."""
        question_lower = question.lower()
        
        if intent == 'listar_cursos':
            return ""
        
        if intent == 'docente_leciona_disciplina':
            match = re.search(
                r'(?:professor(?:a)?|docente)\s+(.+?)\s+(?:leciona|d[aá]|ensina)\s+(.+?)(?:\?|$)',
                question_lower
            )
            if match:
                docente = match.group(1).strip()
                disciplina = match.group(2).strip()
                disciplina = re.sub(r'[\?.,!]+$', '', disciplina).strip()
                return f"{docente}:{disciplina}"
        
        if intent == 'disciplinas_termo':
            if ':' in term:
                return term
            match = re.search(r'(?:termo|semestre)\s+(\d+)', question_lower)
            if match:
                numero = match.group(1)
                curso = re.sub(r'\d+\s*', '', term).strip()
                if curso:
                    return f"{numero}:{curso}"

        if intent == 'trajectory_planning' and ':' not in term:
            inv = re.search(
                r'quero\s+chegar\s+em\s+(.+?),\s+(?:j[aá]\s+)?(?:fiz|cursei|conclui|conclu[ií])\s+(.+?)(?:\?|$)',
                question_lower
            )
            if inv:
                target = re.sub(r'[\?.,!]+$', '', inv.group(1)).strip()
                completed = re.sub(r'[\?.,!]+$', '', inv.group(2)).strip()
                return f"{completed}:{target}"
            fwd = re.search(
                r'(?:j[aá]\s+)?(?:cursei|fiz|conclui|conclu[ií])\s+(.+?)[,:]\s+(?:como\s+)?(?:chego|chegar|fica)\s+(?:em\s+)?(.+?)(?:\?|$)',
                question_lower
            )
            if fwd:
                completed = re.sub(r'[\?.,!]+$', '', fwd.group(1)).strip()
                target = re.sub(r'[\?.,!]+$', '', fwd.group(2)).strip()
                return f"{completed}:{target}"

        return term
    
    def _regex_fallback(self, question: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Fallback para classificação baseada em regex (método legado)."""
        question_lower = question.lower().strip()
        
        for query_type, patterns in self.graph_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, question_lower, re.IGNORECASE)
                if match:
                    if query_type == 'listar_cursos':
                        return True, query_type, ""
                    elif query_type == 'disciplinas_termo' and len(match.groups()) >= 2:
                        termo_num = match.group(1).strip()
                        numeros_extenso = {
                            'primeiro': '1', 'primeira': '1', 'primeir': '1',
                            'segundo': '2', 'segunda': '2', 'segund': '2',
                            'terceiro': '3', 'terceira': '3', 'terceir': '3',
                            'quarto': '4', 'quarta': '4', 'quart': '4',
                            'quinto': '5', 'quinta': '5', 'quint': '5',
                            'sexto': '6', 'sexta': '6', 'sext': '6',
                            'sétimo': '7', 'sétima': '7', 'setimo': '7', 'setima': '7', 'sétim': '7', 'setim': '7',
                            'oitavo': '8', 'oitava': '8', 'oitav': '8',
                            'nono': '9', 'nona': '9', 'non': '9',
                            'décimo': '10', 'décima': '10', 'decimo': '10', 'decima': '10', 'décim': '10', 'decim': '10',
                        }
                        termo_lower = termo_num.lower()
                        for extenso, digito in numeros_extenso.items():
                            if termo_lower.startswith(extenso[:4]):
                                termo_num = digito
                                break
                        curso = match.group(2).strip()
                        curso = re.sub(r'[\?.,!]+$', '', curso).strip()
                        termo = f"{termo_num}:{curso}"
                    elif query_type == 'docente_leciona_disciplina' and len(match.groups()) >= 2:
                        docente = match.group(1).strip()
                        disciplina = match.group(2).strip()
                        docente = re.sub(r'[\?.,!]+$', '', docente).strip()
                        disciplina = re.sub(r'[\?.,!]+$', '', disciplina).strip()
                        termo = f"{docente}:{disciplina}"
                    elif query_type == 'trajectory_planning' and len(match.groups()) >= 2:
                        g1 = re.sub(r'[\?.,!]+$', '', match.group(1)).strip()
                        g2 = re.sub(r'[\?.,!]+$', '', match.group(2)).strip()
                        if re.match(r'quero\s+chegar\s+em\b', question_lower):
                            termo = f"{g2}:{g1}"
                        else:
                            termo = f"{g1}:{g2}"
                    elif match.groups():
                        termo = match.group(1).strip()
                        termo = re.sub(r'[\?.,!]+$', '', termo).strip()
                        termo = re.sub(r'\s+(da|de|do|na|no|em)$', '', termo, flags=re.IGNORECASE).strip()
                    else:
                        termo = ""
                    return True, query_type, termo
        
        return False, None, None
    
    def _resolve_discipline_term(self, termo: str) -> str:
        """Expande sigla/código para o nome completo da disciplina no KG."""
        node_id = self.kg._find_node(termo, "disciplina")
        if node_id:
            nome = self.kg.graph.nodes[node_id].get("nome", "")
            if nome:
                return nome
        return termo

    def _resolve_trajectory_parts(
        self, termo: str
    ) -> Tuple[List[str], str, Optional[str]]:
        """
        Parseia o termo de trajectory_planning → (completed, target, node_id).

        `completed` são as disciplinas já cursadas (texto bruto do aluno),
        `target` é a disciplina alvo (bruta) e `node_id` o nó do KG resolvido
        para o alvo (None se não encontrado).
        """
        from .neurosymbolic_validator import _parse_trajectory_term
        termo_clean = re.split(r'[.!]', termo)[0].strip()
        termo_clean = re.sub(
            r'\s+(?:por\s+onde|como\s+fica|começo|inicio|inicio\.?|começo\.?)\b.*',
            '', termo_clean, flags=re.IGNORECASE
        ).strip()
        if self.kg._find_node(termo_clean, "disciplina"):
            completed, target = [], termo_clean
        else:
            completed, target = _parse_trajectory_term(termo_clean)
        if not target:
            return completed, target, None

        node_id = self.kg._find_node(target, "disciplina")
        if node_id is None:
            grounded = self._find_discipline_in_text(target)
            if grounded:
                node_id = self.kg._find_node(grounded, "disciplina")
        return completed, target, node_id

    def _direct_prereq_edges(self, nomes: List[str]) -> List[Dict]:
        """
        Arestas diretas PREREQUISITO_DE entre as disciplinas de `nomes`,
        com a confiança de cada elo (semântica de bounds do PyReason).
        """
        nomes_set = set(nomes)
        edges = []
        for nome in nomes:
            for prereq in self.kg.get_direct_prerequisites(nome):
                if prereq in nomes_set and prereq != nome:
                    edges.append({
                        "source": prereq,
                        "target": nome,
                        "confidence": round(
                            self.kg.get_prerequisite_confidence(prereq, nome), 2
                        ),
                    })
        return edges

    def _safe_recommended_before(self, termo: str, n: int = 3) -> List[Tuple[str, float]]:
        """
        Regra recommended_before do KGC com guarda: sem embeddings (ou em
        erro) devolve [] - as respostas simbólicas seguem intactas.
        """
        try:
            return self.kg.kgc.get_recommended_before(termo, n=n)
        except Exception:
            return []

    def _recommended_before_section(self, termo: str) -> str:
        """
        Seção "Recomendadas antes" (inferência semântico-simbólica) para
        anexar à resposta de prerequisite_chain. Vazia quando nada é inferido.
        """
        recs = self._safe_recommended_before(termo)
        if not recs:
            return ""
        itens = ", ".join(f"**{nome}** (sim {sim:.0%})" for nome, sim in recs)
        return (
            f"\n\n**Recomendadas antes (inferidas por conteúdo):** {itens}\n"
            "*Regra `recommended_before`: sim_ementa ≥ θ ∧ ¬ancestral ∧ "
            "ordem(A) < ordem(B) - não são pré-requisitos formais, o conteúdo "
            "delas ajuda.*"
        )

    def graph_payload(self, query_type: str, termo: str) -> Optional[Dict]:
        """
        Versão estruturada de query_graph para renderização de grafo no frontend.

        Retorna {type, nodes: [{id, nome, fase?, cursada?}], edges: [{source,
        target, confidence}]} para os intents prerequisite_chain, dependents e
        trajectory_planning - ou None quando não há grafo a exibir. NÃO altera
        query_graph: é uma função paralela, somente leitura sobre o KG.
        """
        if query_type not in (
            'prerequisite_chain', 'dependents', 'trajectory_planning',
            'recommended_before',
        ):
            return None

        if query_type in ('prerequisite_chain', 'dependents', 'recommended_before'):
            nome = self._resolve_discipline_term(termo)

            if query_type == 'prerequisite_chain':
                chain = self.kg.get_prerequisite_chain(nome)
                if not chain:
                    return None
                nomes, vistos = [], set()
                for n in [nome] + chain:
                    if n and n not in vistos:
                        vistos.add(n)
                        nomes.append(n)
                nodes = [{"id": n, "nome": n} for n in nomes]
                edges = self._direct_prereq_edges(nomes)
                for rec_nome, sim in self._safe_recommended_before(nome):
                    if rec_nome not in vistos:
                        vistos.add(rec_nome)
                        nodes.append({
                            "id": rec_nome, "nome": rec_nome, "inferida": True,
                        })
                    edges.append({
                        "source": rec_nome,
                        "target": nome,
                        "confidence": round(sim, 2),
                        "inferida": True,
                    })
                return {
                    "type": "prerequisite_chain",
                    "nodes": nodes,
                    "edges": edges,
                }

            if query_type == 'recommended_before':
                recs = self._safe_recommended_before(nome)
                if not recs:
                    return None
                nodes = [{"id": nome, "nome": nome}]
                edges = []
                for rec_nome, sim in recs:
                    nodes.append({
                        "id": rec_nome, "nome": rec_nome, "inferida": True,
                    })
                    edges.append({
                        "source": rec_nome,
                        "target": nome,
                        "confidence": round(sim, 2),
                        "inferida": True,
                    })
                return {
                    "type": "recommended_before",
                    "nodes": nodes,
                    "edges": edges,
                }

            dependents = [d for d in self.kg.get_dependent_disciplines(nome) if d]
            if not dependents:
                return None
            nomes, vistos = [], set()
            for n in [nome] + dependents:
                if n not in vistos:
                    vistos.add(n)
                    nomes.append(n)
            nodes = [{"id": n, "nome": n} for n in nomes]
            return {
                "type": "dependents",
                "nodes": nodes,
                "edges": self._direct_prereq_edges(nomes),
            }

        from .neurosymbolic_validator import InferenceEngine
        completed, target, node_id = self._resolve_trajectory_parts(termo)
        if not target or not node_id:
            return None
        target = self.kg.graph.nodes[node_id].get("nome", target)

        engine = InferenceEngine(self.kg)
        phases = engine.plan_minimal_path(target, completed)
        if not phases:
            return None

        completed_nomes = []
        for c in completed:
            cid = self.kg._find_node(c, "disciplina")
            nome_c = self.kg.graph.nodes[cid].get("nome") if cid else None
            completed_nomes.append(nome_c or c.strip())

        nodes, vistos = [], set()
        for nome_c in completed_nomes:
            if nome_c and nome_c not in vistos:
                vistos.add(nome_c)
                nodes.append({
                    "id": nome_c, "nome": nome_c, "fase": 0, "cursada": True,
                })
        for i, phase in enumerate(phases, 1):
            for disc in phase:
                if disc and disc not in vistos:
                    vistos.add(disc)
                    nodes.append({
                        "id": disc, "nome": disc, "fase": i, "cursada": False,
                    })
        nomes = [n["id"] for n in nodes]
        return {
            "type": "trajectory_planning",
            "nodes": nodes,
            "edges": self._direct_prereq_edges(nomes),
        }

    def query_graph(self, query_type: str, termo: str) -> Optional[str]:
        """
        Executa uma query no Knowledge Graph e formata a resposta.
        """
        if query_type in ('prerequisite_chain', 'dependents', 'discipline_docentes', 'recommended_before'):
            termo = self._resolve_discipline_term(termo)

        if query_type == 'prerequisite_chain':
            chain = self.kg.get_prerequisite_chain(termo)
            if chain:
                path = f"{termo} ← " + " ← ".join(chain)
                return f"""**Cadeia de pré-requisitos de {termo}:**
{path}

Para cursar **{termo}**, você precisa ter cursado anteriormente:
{chr(10).join(f'- {d}' for d in chain)}

Total: {len(chain)} pré-requisito(s) na cadeia.

*Regras aplicadas: `prereq_transitivity` (fecho transitivo verificado em {len(chain)} aresta(s) do Knowledge Graph)*{self._recommended_before_section(termo)}"""
            else:
                return (
                    f"**{termo}** não possui pré-requisitos ou não foi encontrada no sistema."
                    f"{self._recommended_before_section(termo)}"
                )

        elif query_type == 'recommended_before':
            recs = self._safe_recommended_before(termo)
            if recs:
                linhas = "\n".join(
                    f"- **{nome}** - similaridade de ementa {sim:.0%}"
                    for nome, sim in recs
                )
                return f"""**Recomendadas antes de {termo} (inferidas por conteúdo):**

{linhas}

Estas disciplinas **não são pré-requisitos formais** de {termo}: a recomendação é inferida pela sobreposição das ementas, respeitando a ordem do currículo e ficando fora da cadeia de pré-requisitos.

*Regra aplicada: `recommended_before` - sim_ementa(A,B) ≥ θ ∧ ¬ancestral(A,B) ∧ ¬ancestral(B,A) ∧ ordem(A) < ordem(B)*"""
            if not self.kg._find_node(termo, "disciplina"):
                return (
                    f"Não encontrei a disciplina **{termo}** no sistema. "
                    "Pode me dizer o nome completo dela?"
                )
            return (
                f"Não encontrei disciplinas com conteúdo suficientemente próximo de **{termo}** "
                "fora da cadeia de pré-requisitos para recomendar. "
                f"Os pré-requisitos formais você vê com \"Quais os pré-requisitos de {termo}?\"."
            )
        
        elif query_type == 'dependents':
            dependents = self.kg.get_dependent_disciplines(termo)
            if dependents:
                return f"""**Disciplinas que dependem de {termo}:**

{chr(10).join(f'- {d}' for d in dependents)}

**{termo}** é pré-requisito de {len(dependents)} disciplina(s)."""
            else:
                    return f"Nenhuma disciplina encontrada que tenha **{termo}** como pré-requisito."
        
        elif query_type == 'docente_disciplines':
            disciplinas = self.kg.get_disciplines_of_docente(termo)
            if disciplinas:
                return f"""**Disciplinas lecionadas por {termo}:**

{chr(10).join(f'- {d}' for d in disciplinas)}

O(A) professor(a) **{termo}** leciona {len(disciplinas)} disciplina(s)."""
            else:
                return f"Não encontrei disciplinas lecionadas por **{termo}**."
        
        elif query_type == 'discipline_docentes':
            docentes = self.kg.get_docentes_of_discipline(termo)
            if docentes:
                return f"""**Docentes de {termo}:**

{chr(10).join(f'- {d}' for d in docentes)}"""
            else:
                return f"Não encontrei docentes para **{termo}**."
        
        elif query_type == 'docente_leciona_disciplina':
            if ':' in termo:
                docente, disciplina = termo.split(':', 1)
                disciplinas = self.kg.get_disciplines_of_docente(docente)
                docente_titulo = docente.title()
                
                siglas_disciplinas = {
                    'paa': 'projeto e análise de algoritmos',
                    'pcd': 'programação concorrente e distribuída',
                    'bd': 'banco de dados',
                    'so': 'sistemas operacionais',
                    'ia': 'inteligência artificial',
                    'aed': 'algoritmos e estruturas de dados',
                    'aed1': 'algoritmos e estruturas de dados i',
                    'aed2': 'algoritmos e estruturas de dados ii',
                    'lfa': 'linguagens formais e autômatos',
                    'poo': 'programação orientada a objetos',
                    'cg': 'computação gráfica',
                    'ihc': 'interface humano-computador',
                }
                
                if disciplinas:
                    disc_lower = disciplina.lower()
                    disc_expanded = siglas_disciplinas.get(disc_lower, disc_lower)
                    
                    encontrou = False
                    disciplina_encontrada = None
                    for d in disciplinas:
                        d_lower = d.lower()
                        if disc_expanded in d_lower or disc_lower in d_lower or d_lower in disc_expanded:
                            encontrou = True
                            disciplina_encontrada = d
                            break
                    
                    if encontrou:
                        nome_exibir = disciplina_encontrada if disciplina_encontrada else disciplina.title()
                        return f"**Sim**, o professor **{docente_titulo}** leciona **{nome_exibir}**.\n\nDisciplinas que {docente_titulo} leciona:\n" + "\n".join(f"- {d}" for d in disciplinas)
                    else:
                        return f"**Não**, o professor **{docente_titulo}** **não** leciona **{disciplina.upper() if len(disciplina) <= 4 else disciplina.title()}**.\n\nDisciplinas que {docente_titulo} leciona:\n" + "\n".join(f"- {d}" for d in disciplinas)
                else:
                    return f"Não encontrei informações sobre as disciplinas de **{docente_titulo}**."
            else:
                return "Formato de consulta inválido."

        elif query_type == 'artigos_sobre':
            artigos = self.kg.get_artigos_sobre(termo)
            if artigos:
                resultado = f"**Artigos sobre '{termo}':**\n\n"
                for art in artigos[:5]:
                    resultado += f"- **Art. {art['numero']}** ({art['documento']}): {art['conteudo']}\n\n"
                return resultado
            else:
                return f"Não encontrei artigos sobre **{termo}**."
        
        elif query_type == 'faqs':
            faqs = self.kg.get_faqs_sobre(termo)
            if faqs:
                resultado = f"**Perguntas frequentes sobre '{termo}':**\n\n"
                for faq in faqs[:5]:
                    resultado += f"**P:** {faq['pergunta']}\n**R:** {faq['resposta']}\n\n"
                return resultado
            else:
                return f"Não encontrei FAQs sobre **{termo}**."
        
        elif query_type == 'docentes_by_area':
            docentes = self.kg.get_docentes_by_area(termo)
            if docentes:
                return f"""**Professores especialistas em {termo}:**

{chr(10).join(f'- {d}' for d in docentes)}

Total: {len(docentes)} docente(s) trabalham com **{termo}**."""
            else:
                return f"Não encontrei docentes especialistas em **{termo}**."
        
        elif query_type == 'docente_areas':
            areas = self.kg.get_areas_of_docente(termo)
            if areas:
                return f"""**Áreas de especialização de {termo}:**

{chr(10).join(f'- {a}' for a in areas)}

O(A) professor(a) **{termo}** é especialista em {len(areas)} área(s)."""
            else:
                grounded = self._find_docente_in_text(termo)
                if grounded and self.kg._normalize_text(grounded) != self.kg._normalize_text(termo):
                    return self.query_graph('docente_areas', grounded)
                return (
                    "Não consegui identificar esse docente na base. "
                    "De qual professor você quer saber as áreas de pesquisa? "
                    "Por exemplo: *qual a área da professora Lilian Berton?*"
                )

        elif query_type == 'docente_info':
            info = self.kg.get_docente_info(termo)
            if not info:
                grounded = self._find_docente_in_text(termo)
                if grounded and self.kg._normalize_text(grounded) != self.kg._normalize_text(termo):
                    return self.query_graph('docente_info', grounded)
                return (
                    "Não consegui identificar esse docente na base. "
                    "De qual professor você quer as informações (email, sala)?"
                )
            resultado = f"**Informações de {info['nome']}:**\n\n"
            if info.get('email'):
                resultado += f"- **Email:** {info['email']}\n"
            if info.get('sala'):
                resultado += f"- **Sala:** {info['sala']}\n"
            if info.get('areas'):
                resultado += f"- **Áreas:** {info['areas']}\n"
            return resultado
        
        elif query_type == 'matriz_info':
            info = self.kg.get_info_matriz(termo)
            if info:
                resultado = f"**Matriz Curricular - {info['nome']}:**\n\n"
                if info.get('sigla'):
                    resultado += f"- **Sigla:** {info['sigla']}\n"
                if info.get('duracao_termos'):
                    resultado += f"- **Duração:** {info['duracao_termos']} termos (semestres)\n"
                if info.get('carga_horaria'):
                    resultado += f"- **Carga Horária Total:** {info['carga_horaria']} horas\n"
                if info.get('coordenador'):
                    resultado += f"- **Coordenador(a):** {info['coordenador']}\n"
                if info.get('vice_coordenador'):
                    resultado += f"- **Vice-Coordenador(a):** {info['vice_coordenador']}\n"
                resultado += f"\nO curso possui disciplinas obrigatórias organizadas por termo, além de eletivas nos Grupos 1, 2, 3 e eletivas extensionistas."
                return resultado
            else:
                return f"Não encontrei matriz curricular para **{termo}**."
        
        elif query_type == 'coordenador_curso':
            info = self.kg.get_coordenador(termo)
            if info and (info.get('coordenador') or info.get('vice_coordenador')):
                curso_nome = info.get('curso') or info.get('nome') or termo
                resultado = f"**Coordenação do curso {curso_nome}**"
                if info.get('sigla'):
                    resultado += f" ({info['sigla']})"
                resultado += ":\n\n"
                if info.get('coordenador'):
                    resultado += f"- **Coordenador(a):** {info['coordenador']}\n"
                if info.get('vice_coordenador'):
                    resultado += f"- **Vice-Coordenador(a):** {info['vice_coordenador']}\n"
                return resultado
            else:
                return f"Não encontrei informações de coordenação para **{termo}**."
        
        elif query_type == 'listar_cursos':
            cursos = self.kg.get_all_cursos()
            if cursos:
                resultado = "**Cursos de Graduação da UNIFESP ICT:**\n\n"
                for i, curso in enumerate(cursos, 1):
                    nome = curso.get('nome', '')
                    sigla = curso.get('sigla', '')
                    duracao = curso.get('duracao_termos', '')
                    resultado += f"{i}. **{nome}**"
                    if sigla:
                        resultado += f" ({sigla})"
                    if duracao:
                        resultado += f" - {duracao} termos"
                    resultado += "\n"
                return resultado
            else:
                return "Não encontrei informações sobre os cursos."
        
        elif query_type == 'disciplinas_termo':
            if ':' in termo:
                termo_num, curso = termo.split(':', 1)
                try:
                    termo_int = int(termo_num)
                except ValueError:
                    return f"Termo inválido: {termo_num}"
                
                disciplinas = self.kg.get_disciplinas_do_termo(curso, termo_int)
                if disciplinas:
                    resultado = f"**Disciplinas do Termo {termo_int} de {curso.upper()}:**\n\n"
                    for d in disciplinas:
                        resultado += f"- {d['nome']} ({d['creditos']} créditos)\n"
                    return resultado
                else:
                    return f"Não encontrei disciplinas do termo {termo_int} para **{curso}**."
            else:
                return f"Formato inválido para consulta de termo."
        
        elif query_type == 'todos_termos_curso':
            termos = self.kg.get_todos_termos_do_curso(termo)
            if termos:
                info = self.kg.get_info_matriz(termo)
                curso_nome = info.get('nome', termo.upper()) if info else termo.upper()
                duracao = info.get('duracao_termos', str(len(termos))) if info else str(len(termos))
                
                resultado = f"**Disciplinas da Matriz Curricular de {curso_nome}**\n"
                resultado += f"*Total de {duracao} termos (semestres)*\n\n"
                
                for termo_num in sorted(termos.keys()):
                    disciplinas = termos[termo_num]
                    total_creditos = sum(int(d.get('creditos', 0)) for d in disciplinas)
                    resultado += f"### Termo {termo_num} ({total_creditos} créditos)\n"
                    for d in disciplinas:
                        resultado += f"- {d['nome']} ({d['creditos']} créditos)\n"
                    resultado += "\n"
                
                return resultado
            else:
                return f"Não encontrei disciplinas para o curso **{termo}**."
        
        elif query_type == 'eletivas_curso':
            grupo_filtro = None
            curso_limpo = termo
            
            grupo_match = re.search(r'(?:grupo\s+|g)(\d+)', termo, re.IGNORECASE)
            if grupo_match:
                num_grupo = grupo_match.group(1)
                grupo_filtro = f"grupo{num_grupo}"
                curso_limpo = re.sub(r'\s*(?:grupo\s+|g)\d+\s*(?:de|do|da)?\s*', '', termo, flags=re.IGNORECASE).strip()
            
            eletivas = self.kg.get_eletivas_do_curso(curso_limpo, grupo=grupo_filtro)
            if eletivas:
                grupos = {}
                for e in eletivas:
                    grupo = e.get('grupo', 'outro')
                    if grupo not in grupos:
                        grupos[grupo] = []
                    grupos[grupo].append(e['nome'])
                
                if grupo_filtro:
                    resultado = f"**Eletivas do Grupo {num_grupo} para {curso_limpo.upper()}:**\n\n"
                else:
                    resultado = f"**Eletivas disponíveis para {curso_limpo.upper()}:**\n\n"
                
                ordem_grupos = ['eletiva_grupo1', 'eletiva_grupo2', 'eletiva_grupo3', 'eletiva_extensionista']
                grupos_ordenados = sorted(grupos.keys(), key=lambda x: ordem_grupos.index(x) if x in ordem_grupos else 99)
                
                for grupo in grupos_ordenados:
                    disciplinas = grupos[grupo]
                    nomes_grupos = {
                        'eletiva_grupo1': 'Grupo 1 - Eletivas Limitadas de Ciência da Computação',
                        'eletiva_grupo2': 'Grupo 2 - Eletivas de Matemática e Computação',
                        'eletiva_grupo3': 'Grupo 3 - Eletivas de Ciências Humanas, Econômicas e Sociais',
                        'eletiva_extensionista': 'Eletivas Extensionistas',
                    }
                    grupo_nome = nomes_grupos.get(grupo, grupo.replace('_', ' ').title())
                    resultado += f"**{grupo_nome}:**\n"
                    for d in disciplinas:
                        resultado += f"- {d}\n"
                    resultado += "\n"
                
                resultado += f"\n**Total:** {len(eletivas)} eletivas disponíveis."
                return resultado
            else:
                curso_node = self.kg._find_node(curso_limpo, "curso") or \
                             self.kg._find_node(curso_limpo, "matriz_curricular")
                if curso_node:
                    nome_curso = self.kg.graph.nodes[curso_node].get("nome", curso_limpo)
                    return (
                        f"A base de dados não lista eletivas específicas para **{nome_curso}**. "
                        "A matriz curricular prevê vagas de eletivas (Eletiva I, II, ...), mas o "
                        "detalhamento dos grupos de eletivas desse curso não está disponível - "
                        "consulte a coordenação ou o portal da UNIFESP."
                    )
                grounded = self._find_curso_in_text(curso_limpo)
                if grounded:
                    return self.query_graph('eletivas_curso', grounded)
                return (
                    "De qual curso você quer ver as eletivas? "
                    "Por exemplo: *eletivas de BCC* ou *eletivas do BCT*. 😊"
                )

        elif query_type == 'critical_disciplines':
            from .neurosymbolic_validator import InferenceEngine
            engine = InferenceEngine(self.kg)
            critical = engine.critical_disciplines(min_dependents=2)
            if not critical:
                return "Não encontrei disciplinas com dependentes suficientes no grafo."

            nome_curso_filtro = None
            if termo.strip():
                curso_node = self.kg._find_node(termo.strip(), "curso") or \
                             self.kg._find_node(termo.strip().upper(), "curso")
                if not curso_node:
                    grounded = self._find_curso_in_text(termo)
                    if grounded:
                        curso_node = self.kg._find_node(grounded, "curso")
                if curso_node:
                    nome_curso_filtro = self.kg.graph.nodes[curso_node].get("nome", termo)
                    discs_do_curso = {
                        self.kg.graph.nodes[v].get("nome", "").lower()
                        for _, v, d in self.kg.graph.out_edges(curso_node, data=True)
                        if d.get("relacao") in ("INCLUI", "OFERECE")
                    }
                    critical = [(nome, n) for nome, n in critical if nome.lower() in discs_do_curso]

            vistos, unicos = set(), []
            for nome, n_deps in critical:
                chave = self.kg._normalize_text(nome)
                if chave not in vistos:
                    vistos.add(chave)
                    unicos.append((nome, n_deps))
            critical = unicos

            if nome_curso_filtro:
                resultado = (
                    f"**Disciplinas mais críticas de {nome_curso_filtro}** "
                    "(pela regra `critical_discipline`: ∀x: |dependentes(x)| ≥ θ)\n\n"
                )
            else:
                resultado = (
                    "**Disciplinas mais críticas do currículo** "
                    "(pela regra `critical_discipline`: ∀x: |dependentes(x)| ≥ θ)\n\n"
                    "*Considerando todos os cursos do ICT - cite um curso para filtrar "
                    "(ex.: \"disciplinas críticas de BCC\").*\n\n"
                )
            resultado += "| Disciplina | Dependentes |\n|---|---|\n"
            for nome, n_deps in critical[:12]:
                resultado += f"| {nome} | {n_deps} |\n"
            resultado += f"\n*Critério: mínimo {2} disciplinas que dependem direta ou indiretamente.*"
            return resultado

        elif query_type == 'co_prerequisite':
            from .neurosymbolic_validator import InferenceEngine
            engine = InferenceEngine(self.kg)
            co_prereqs = engine.find_co_prerequisites(termo)
            if not co_prereqs:
                node_id = self.kg._find_node(termo, "disciplina")
                if node_id:
                    nome = self.kg.graph.nodes[node_id].get("nome", termo)
                    return f"**{nome}** não compartilha pré-requisitos com nenhuma outra disciplina."
                return f"Não encontrei **{termo}** na base de dados."
            node_id = self.kg._find_node(termo, "disciplina")
            nome_disc = self.kg.graph.nodes[node_id].get("nome", termo) if node_id else termo
            resultado = f"**Disciplinas com pré-requisitos em comum com {nome_disc}** (co-pré-requisitos):\n\n"
            for d in co_prereqs:
                resultado += f"- {d}\n"
            resultado += f"\n*Essas disciplinas compartilham ao menos um pré-requisito com {nome_disc}.*"
            return resultado

        elif query_type == 'trajectory_planning':
            from .neurosymbolic_validator import InferenceEngine
            completed, target, node_id = self._resolve_trajectory_parts(termo)
            if not target:
                return "Por favor, informe a disciplina alvo (ex: 'Compiladores')."

            if node_id:
                target = self.kg.graph.nodes[node_id].get("nome", target)
            else:
                return (
                    "Não consegui identificar a disciplina alvo na sua pergunta. "
                    "Me diga qual disciplina você quer alcançar - por exemplo: "
                    "\"Quero chegar em Compiladores, já fiz Matemática Discreta\"."
                )

            engine = InferenceEngine(self.kg)
            phases = engine.plan_minimal_path(target, completed)

            if phases is None:
                return (
                    f"Não encontrei **{target}** na base de dados da UNIFESP ICT, "
                    "ou há uma inconsistência no grafo de pré-requisitos."
                )

            if len(phases) == 1 and phases[0] == [target]:
                msg = f"Você já pode cursar **{target}**"
                if completed:
                    msg += f" com as disciplinas que já cursou ({', '.join(completed)})"
                msg += " - todos os pré-requisitos estão atendidos."
                return msg

            total = sum(len(p) for p in phases)
            conf_por_disc, path_bound = engine.path_confidence(phases)

            resultado = f"**Caminho mínimo para {target}**"
            if completed:
                resultado += f"\n*Cursadas: {', '.join(completed)}*"
            resultado += f"\n*{len(phases)} fase(s) · {total} disciplina(s) a cursar*\n\n"

            for i, phase in enumerate(phases, 1):
                plural = "s" if len(phase) > 1 else ""
                resultado += f"**Fase {i}** *(em paralelo)*\n"
                for disc in phase:
                    conf = conf_por_disc.get(disc)
                    if conf is not None:
                        resultado += f"- {disc} *(confiança {conf:.0%})*\n"
                    else:
                        resultado += f"- {disc}\n"
                resultado += "\n"

            resultado += (
                "*Disciplinas na mesma fase podem ser cursadas simultaneamente. "
                "Verifique a oferta semestral no portal da UNIFESP.*"
            )
            if path_bound < 1.0:
                resultado += (
                    f"\n\n*Confiança do caminho (bound inferior): {path_bound:.0%} - "
                    "alguns elos de pré-requisito têm confiança parcial no grafo.*"
                )
            resultado += (
                "\n\n*Regras aplicadas: `minimal_path` (BFS topológico) + "
                "`unlock_condition` (verificação de pré-requisitos por fase)*"
            )
            if not completed:
                resultado += (
                    "\n\n*💡 Dica: informe disciplinas já cursadas separadas por vírgula para "
                    "um caminho personalizado. Ex: \"já cursei Cálculo 1, AED I: como chego em Compiladores?\"*"
                )
            return resultado

        return None
    
    def get_graph_context(self, question: str) -> Optional[str]:
        """
        Tenta responder usando o grafo. Retorna None se não for uma pergunta de grafo.
        """
        use_graph, query_type, termo = self.should_use_graph(question)
        
        if use_graph and query_type and termo:
            return self.query_graph(query_type, termo)
        
        return None
    
    def enrich_context(self, question: str, disciplina: Optional[str] = None) -> str:
        """
        Enriquece o contexto com informações do grafo (mesmo para perguntas não-grafo).
        Útil para adicionar contexto relacional às respostas do RAG tradicional.
        """
        enrichments = []
        
        if disciplina:
            prereqs = self.kg.get_prerequisite_chain(disciplina, max_depth=2)
            if prereqs:
                enrichments.append(f"Pré-requisitos de {disciplina}: {', '.join(prereqs[:3])}")
            
            docentes = self.kg.get_docentes_of_discipline(disciplina)
            if docentes:
                enrichments.append(f"Docentes de {disciplina}: {', '.join(docentes)}")
        
        return "\n".join(enrichments) if enrichments else ""
