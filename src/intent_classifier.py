"""
Classificador de Intenção baseado em Embeddings Semânticos.

Substitui regex frágil por similaridade semântica, permitindo:
- Entender paráfrases ("o que preciso antes de BD?" → prerequisite_chain)
- Robustez a erros de digitação
- Menos manutenção de patterns
"""

import re
import numpy as np
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    """Resultado da classificação de intenção."""
    intent: str
    term: str
    confidence: float
    method: str  # 'regex', 'embeddings', ou 'llm'


class IntentClassifier:
    """
    Classificador híbrido de intenção:
    1. Regex rápido para casos óbvios
    2. Embeddings para classificação semântica
    3. Extração de termos inteligente
    """
    
    # Exemplos de treinamento por intenção (quanto mais, melhor)
    INTENT_EXAMPLES = {
        'ementa_disciplina': [
            "o que é Geometria Analítica",
            "o que é Cálculo Numérico",
            "o que é Inteligência Artificial",
            "descreva a disciplina Algoritmos",
            "o que se estuda em Compiladores",
            "o que aprendo em Banco de Dados",
            "do que trata Álgebra Linear",
            "qual é o conteúdo de Física 1",
            "me explique o que é Redes de Computadores",
            "tem a ementa dela",
            "tem a ementa",
            "qual a ementa",
            "me mostra a ementa",
            "quero ver a ementa",
            "qual é a ementa desta disciplina",
            "a ementa dela",
            "ementa de interação humano-computador",
            "o que você sabe sobre a disciplina de Interação Humano-Computador",
            "fale sobre a disciplina de Cálculo 1",
            "me conta sobre Banco de Dados",
            "o que há sobre Compiladores",
            "fala sobre Álgebra Linear",
            "o que sabe sobre Redes de Computadores",
            "me fale sobre a disciplina de Engenharia de Software",
            "explique a disciplina Computação Quântica",
            "explique Banco de Dados",
            "me explique o que é Compiladores",
            "descreva Álgebra Linear",
        ],
        'prerequisite_chain': [
            "quais são os pré-requisitos de banco de dados",
            "pré-requisitos para cursar algoritmos 2",
            "o que preciso fazer antes de inteligência artificial",
            "disciplinas necessárias para fazer cálculo 2",
            "preciso de quais matérias para cursar compiladores",
            "cadeia de pré-requisitos de estrutura de dados",
            "quais matérias devo fazer antes de redes",
            "requisitos para fazer programação orientada a objetos",
            # Paráfrases adicionais
            "o que eu preciso pra fazer IA",
            "preciso de o que pra fazer compiladores",
            "antes de cursar redes preciso de o que",
            "para fazer banco de dados preciso cursar o que antes",
            "quais disciplinas são necessárias antes de IA",
        ],
        'recommended_before': [
            "o que é bom fazer antes de projeto e análise de algoritmos",
            "o que ajuda a fazer antes de compiladores",
            "quais disciplinas são recomendadas antes de banco de dados",
            "o que vale a pena cursar antes de inteligência artificial",
            "que matéria é útil fazer antes de redes de computadores",
            "o que é legal ter feito antes de cálculo numérico",
            "disciplinas recomendadas antes de estrutura de dados",
        ],
        'dependents': [
            "quais disciplinas dependem de cálculo 1",
            "para que serve algoritmos como pré-requisito",
            "quais matérias usam banco de dados como requisito",
            "disciplinas que exigem lógica de programação",
            "o que posso cursar depois de algoritmos",
        ],
        'discipline_docentes': [
            "quem leciona banco de dados",
            "professor de cálculo numérico",
            "quem dá aula de programação",
            "docentes de algoritmos e estruturas de dados",
            "quem ensina inteligência artificial",
            "qual professor ministra redes de computadores",
            "quem são os professores de compiladores",
            "quais professores dão cálculo",
            "quais docentes dão álgebra linear",
            "quais professores ministram física",
            "quais são os docentes de probabilidade",
            "quais professores ensinam programação orientada a objetos",
            "professores que dão cálculo em várias variáveis",
            "quem são os professores de equações diferenciais",
            "qual o professor responsável por cálculo numérico",
            "quem é o responsável pela disciplina de redes",
        ],
        'docente_disciplines': [
            "quais disciplinas o professor João leciona",
            "matérias que a professora Maria ensina",
            "o que o Álvaro Fazenda leciona",
            "disciplinas do professor Tiago Carvalho",
            "quais matérias a Daniela dá",
        ],
        'docente_info': [
            "qual o email do professor João",
            "sala do professor Álvaro",
            "como entro em contato com a professora Maria",
            "onde fica a sala do docente Tiago",
            "informações de contato do professor",
            "email da professora Daniela",
            "me fale sobre o professor João",
            "quem é a professora Maria",
            "informações sobre o docente Álvaro",
            "fale sobre a professora Lilian",
        ],
        'docente_areas': [
            "qual a área de pesquisa do professor",
            "em que o Álvaro é especialista",
            "áreas de atuação do professor Tiago",
            "o que o professor João pesquisa",
            "especialização do docente Maria",
            "área de conhecimento do professor",
        ],
        'docentes_by_area': [
            "professores que trabalham com inteligência artificial",
            "quem pesquisa machine learning",
            "docentes especialistas em redes neurais",
            "professores de visão computacional",
            "quem trabalha com processamento de linguagem natural",
            "especialistas em segurança da informação",
        ],
        'docente_leciona_disciplina': [
            "o professor João leciona banco de dados",
            "a professora Maria dá aula de cálculo",
            "o Álvaro ensina inteligência artificial",
            "o Tiago ministra visão computacional",
        ],
        'disciplinas_termo': [
            "disciplinas do termo 5 de BCC",
            "matérias do primeiro semestre de computação",
            "o que tem no termo 3 de engenharia",
            "grade do segundo período de ciência da computação",
            "disciplinas do 4 termo de matemática computacional",
        ],
        'todos_termos_curso': [
            "todas as disciplinas de computação",
            "grade completa de BCC",
            "disciplinas por termo de engenharia",
            "matriz curricular completa de ciência da computação",
            "listar todas matérias do curso",
            # Paráfrases adicionais
            "grade de ciência da computação",
            "grade curricular de computação",
            "disciplinas do curso de BCC",
            "ver todas as matérias de computação",
            "mostrar grade de engenharia",
        ],
        'matriz_info': [
            "informações sobre o curso de computação",
            "quantos termos tem BCC",
            "duração do curso de engenharia",
            "carga horária total de ciência da computação",
            "estrutura curricular de matemática computacional",
        ],
        'eletivas_curso': [
            "eletivas de computação",
            "disciplinas eletivas do BCC",
            "quais são as eletivas disponíveis",
            "eletivas do grupo 1 de ciência da computação",
            "opcionais de engenharia",
        ],
        'coordenador_curso': [
            "quem é o coordenador de computação",
            "coordenação do curso de BCC",
            "vice-coordenador de engenharia",
            "quem coordena ciência da computação",
        ],
        'listar_cursos': [
            "quais cursos a unifesp oferece",
            "cursos disponíveis no ICT",
            "listar cursos de graduação",
            "quais são os cursos da unifesp",
            # Mais específicos para evitar confusão
            "que cursos tem na unifesp",
            "cursos oferecidos pelo ICT",
            "lista de cursos da unifesp sjc",
        ],
        'trajectory_planning': [
            "qual o caminho para chegar em Compiladores",
            "como chego em Inteligência Artificial partindo do zero",
            "preciso cursar o quê para chegar em Banco de Dados",
            "quais disciplinas devo fazer até conseguir cursar Redes",
            "sequência de disciplinas para chegar em Compiladores",
            "planejamento para cursar Projeto e Análise de Algoritmos",
            "já cursei Cálculo 1, o que falta para chegar em Algoritmos II",
            "dado que já fiz AED 1 e Cálculo 2, como chego em IA",
            "quero chegar em Compiladores, por onde começo",
            "caminho mínimo até Visão Computacional",
        ],
        'critical_disciplines': [
            "quais disciplinas são críticas no currículo",
            "quais as disciplinas mais importantes do curso",
            "quais disciplinas desbloqueiam mais outras",
            "quais disciplinas têm mais dependentes",
            "quais matérias são fundamentais para o curso",
            "disciplinas essenciais de BCC",
            "quais disciplinas mais desbloqueiam outras no currículo",
        ],
        'artigos_sobre': [
            "artigos sobre atividades complementares",
            "o que o regimento diz sobre faltas",
            "normas sobre trancamento",
            "regras de aprovação",
        ],
        'faqs': [
            "dúvidas frequentes sobre matrícula",
            "perguntas comuns sobre atividades complementares",
            "FAQ sobre estágio",
        ],
    }
    
    # Regex rápido para casos óbvios (fallback/boost)
    QUICK_PATTERNS = {
        # recommended_before ANTES de ementa_disciplina: "o que é BOM fazer
        # antes de X" casaria com o "o que é" da ementa. Exige bom/útil/ajuda/
        # recomendado/vale a pena — NUNCA preciso/devo, que é prerequisite_chain.
        'recommended_before': (
            r'(?:bom|legal|[uú]til|recomendad\w*|indicad\w*|vale\s+a\s+pena|ajuda(?:ria)?)\s+'
            r'(?:a\s+)?(?:fazer|cursar|estudar|ter\s+feito)?\s*antes\s+de\b'
        ),
        # ementa_disciplina tem PRIORIDADE sobre prerequisite_chain — "o que é X?" ≠ pré-req
        'ementa_disciplina': (
            r'ementa\b'
            r'|o\s+que\s+[eé]\s+'
            r'|o\s+que\s+(?:se\s+)?(?:estuda|aprende)\s+em\b'
            r'|descreva\s+(?:a?\s+)?(?:disciplina\s+)?'
            r'|explique?\s+(?:a\s+)?(?:disciplina\s+)?'
            r'|o\s+que\s+(?:voc[eê]\s+)?sabe\s+sobre\b'
            r'|(?:me\s+)?(?:fale|conte|conta|fala)\s+sobre\b'
            r'|o\s+que\s+h[aá]\s+sobre\b'
            r'|carga\s+hor[aá]ria\b'
            r'|bibliograf'
        ),
        'prerequisite_chain': r'pr[eé][-\s]?requisitos?',
        'dependents': r'depend(?:e|em)\s+de|desbloqueia',
        'critical_disciplines': (
            r'disciplinas?\s+cr[ií]ticas?'
            r'|mais\s+(?:importantes?|fundamentais?|essenciais?)'
            r'|mais\s+dependentes?'
            r'|desbloqueiam\s+mais'
            r'|mais\s+disciplinas?\s+depend'
            r'|maior\s+n[uú]mero\s+de\s+dependentes?'
            r'|mais\s+pré-?requisitos?\s+(?:de\s+outras?|para\s+outras?)'
        ),
        'discipline_docentes': r'quem\s+(?:leciona|d[aá]|ensina)|(?:quais?\s+)?(?:professore?s?|docentes?)\s+(?:d[aã]o|que\s+(?:leciona|d[aã]o|ensina|ministra))|(?:professor(?:es|a)?|docentes?)\s+respons[aá]ve(?:l|is)\s+(?:por|pel[ao])|quem\s+(?:[eé]\s+)?(?:o\s+|a\s+)?respons[aá]vel\s+(?:por|pel[ao])',
        'docente_info': r'(?:email|e-mail|sala|contato)\s+(?:de|do|da)',
        'listar_cursos': r'cursos?\s+(?:da\s+)?(?:unifesp|ict)',
        'eletivas_curso': r'eletivas?',
        'coordenador_curso': r'coordena(?:dor|ção)',
        'trajectory_planning': (
            r'caminho\s+(?:m[ií]nimo\s+)?(?:para|até|ate)\b'
            r'|como\s+(?:chego|chegar)\s+(?:em|até|ate)\b'
            r'|sequência\s+(?:de\s+disciplinas?\s+)?para\b'
            r'|planejamento\s+para\s+cursar\b'
            r'|(?:j[aá]\s+)?(?:fiz|cursei|conclui|conclu[ií])\s+.{3,}'
            r'|quero\s+chegar\s+em\b'
        ),
    }
    
    # Padrões para extração de termos por intenção
    TERM_PATTERNS = {
        'ementa_disciplina': [
            r'o\s+que\s+[eé]\s+(?:o\s+|a\s+)?([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
            r'o\s+que\s+(?:se\s+)?(?:estuda|aprende)\s+em\s+(.+?)(?:\?|$)',
            r'descreva\s+a?\s+disciplina\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'do\s+que\s+trata\s+(.+?)(?:\?|$)',
            r'ementa\s+d[aeo]\s+(.+?)(?:\?|$)',
            r'ementa\s+(?:de\s+)?([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
            r'(?:tem|ver|mostra)\s+(?:a\s+)?ementa\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'o\s+que\s+(?:voc[eê]\s+)?sabe\s+sobre\s+(?:a\s+)?(?:disciplina\s+(?:de\s+)?)?(.+?)(?:\?|$)',
            r'(?:me\s+)?(?:fale|conte|conta|fala)\s+sobre\s+(?:a\s+)?(?:disciplina\s+(?:de\s+)?)?(.+?)(?:\?|$)',
            r'o\s+que\s+h[aá]\s+sobre\s+(?:a\s+)?(?:disciplina\s+(?:de\s+)?)?(.+?)(?:\?|$)',
            r'carga\s+hor[aá]ria\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            r'(?:qual\s+(?:a\s+)?)?carga\s+hor[aá]ria\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            r'bibliograf(?:ia)?\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            r'explique?\s+(?:a\s+)?(?:disciplina\s+(?:de\s+)?)?(.+?)(?:\?|$)',
        ],
        'recommended_before': [
            r'antes\s+de\s+(?:fazer\s+|cursar\s+|estudar\s+)?(.+?)(?:\?|$)',
        ],
        'prerequisite_chain': [
            r'pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
            r'antes\s+de\s+(?:fazer\s+|cursar\s+)?(.+?)(?:\?|$)',
            r'para\s+(?:fazer|cursar)\s+(.+?)(?:\?|$)',
            # "E de Compiladores, quais são os pré-requisitos?"
            r'^e\s+(?:de|sobre)\s+(.+?)(?:,|\?|$)',
            # "E de X? / E sobre X?"
            r'^e\s+(?:de|sobre)\s+(.+?)(?:,|\s+quais?|\s+os?|\?)',
        ],
        'dependents': [
            r'depend(?:e|em)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            r'(?:usam?|precisam?|exigem?)\s+(.+?)\s+como',
            r'(?:o\s+que\s+)?(.+?)\s+desbloqueia(?:\?|$)',
        ],
        'discipline_docentes': [
            # "Quem leciona Compiladores?" / "Quais docentes dão Cálculo Numérico?"
            # "professor responsável por SEDO" / "quem é o responsável pela disciplina de IHC"
            r'respons[aá]ve(?:l|is)\s+(?:por|pel[ao])\s+(?:a\s+|o\s+)?(?:disciplina\s+(?:de\s+)?|mat[eé]ria\s+(?:de\s+)?)?(.+?)(?:\?|$)',
            r'(?:leciona|ensina|ministra)\s+(.+?)(?:\?|$)',
            r'd[aá]\s+aula\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'(?:professore?s?|docentes?)\s+(?:d[aã]o|de|da|do)\s+(.+?)(?:\?|$)',
            r'd[aã]o\s+(.+?)(?:\?|$)',
            r'aula\s+de\s+(.+?)(?:\?|$)',
            # "Quem leciona?" (sem disciplina - deve retornar vazio para pegar do contexto)
        ],
        'docente_disciplines': [
            r'(?:professor(?:a)?|docente)\s+(.+?)\s+(?:leciona|ensina)',
            r'(?:o\s+|a\s+)?(.+?)\s+(?:leciona|ensina|d[aá])',
        ],
        'docente_info': [
            r'(?:email|sala|contato)\s+(?:de|do|da)\s+(?:professor(?:a)?\s+)?(.+?)(?:\?|$)',
            r'(?:professor(?:a)?|docente)\s+(.+?)(?:\?|$)',
        ],
        'docente_areas': [
            r'[aá]reas?\s+(?:de|do|da)\s+(?:professor(?:a)?\s+)?(.+?)(?:\?|$)',
            r'(?:o\s+|a\s+)?(.+?)\s+(?:pesquisa|trabalha|atua)',
        ],
        'docentes_by_area': [
            r'(?:trabalham?|pesquisam?|especialistas?)\s+(?:com|em)\s+(.+?)(?:\?|$)',
            r'(?:professore?s?|docentes?)\s+(?:de|em)\s+(.+?)(?:\?|$)',
        ],
        'disciplinas_termo': [
            r'(?:termo|semestre|per[ií]odo)\s+(\d+)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
        ],
        'matriz_info': [
            r'(?:curso|matriz)\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
            r'(?:de|do|da)\s+(.+?)(?:\?|$)',
        ],
        'eletivas_curso': [
            r'eletivas?\s+(?:de|do|da|para)\s+(.+?)(?:\?|$)',
        ],
        'coordenador_curso': [
            r'coordena(?:dor(?:a)?|ção)\s+(?:de|do|da|d[eo])\s+(.+?)(?:\?|$)',
            r'coordena(?:dor(?:a)?)\s+(.+?)(?:\?|$)',
        ],
        'todos_termos_curso': [
            r'grade\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'disciplinas?\s+(?:do\s+curso\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
        ],
        'trajectory_planning': [
            # "já cursei/fiz X, Y: como chego em Z" — 2 grupos, most specific first
            r'(?:j[aá]\s+)?(?:cursei|fiz|conclui|conclu[ií])\s+(.+?)[,:]\s+(?:como\s+)?(?:chego|chegar|fica)\s+(?:em\s+)?([^.!?]+?)(?:[.!?]|$)',
            # "já fiz X, Y, como fica?" — completed only
            r'(?:j[aá]\s+)?(?:fiz|conclui|conclu[ií])\s+(.+?)[,.]?\s+(?:como\s+fica|o\s+que\s+falta)\s*\??',
            # "quero chegar em TARGET, já fiz/cursei COMPLETED" — target first
            r'quero\s+chegar\s+em\s+([^,.!?]+?),\s+(?:j[aá]\s+)?(?:fiz|cursei|conclui|conclu[ií])\s+([^.!?]+?)(?:[.!?]|$)',
            # "quero chegar em X" — para em qualquer pontuação
            r'quero\s+chegar\s+em\s+([^,.!?]+?)(?:[,.!?]|$)',
            # "caminho (mínimo) para [chegar em] X"
            r'caminho\s+(?:m[ií]nimo\s+)?para\s+(?:chegar\s+(?:em|at[eé])\s+)?([^.!?]+?)(?:[.!?]|$)',
            # "como chego em X" / "como chegar em X"
            r'como\s+cheg(?:o|ar)\s+(?:em|at[eé])\s+([^.!?]+?)(?:[.!?]|$)',
            # "sequência de disciplinas para X"
            r'sequência\s+(?:de\s+disciplinas?\s+)?para\s+(?:cursar\s+)?([^.!?]+?)(?:[.!?]|$)',
            # "planejamento para cursar X"
            r'planejamento\s+para\s+cursar\s+([^.!?]+?)(?:[.!?]|$)',
            # generic "para chegar em X" / "até X"
            r'(?:chegar?\s+(?:em|at[eé])|at[eé])\s+([^.!?]+?)(?:[.!?]|$)',
        ],
    }
    
    # Prompt para extração de intent + termo via LLM
    _LLM_PROMPT = """Você é um extrator de intenção para o assistente da UNIFESP ICT.

Dada a pergunta do usuário, retorne um JSON com:
- "intent": uma das intenções abaixo
- "term": o nome exato da disciplina, docente ou curso mencionado
- "completed": lista de disciplinas já cursadas (só para trajectory_planning, senão [])

INTENÇÕES:
ementa_disciplina   — o que é / ementa / conteúdo / explique uma disciplina
prerequisite_chain  — pré-requisitos para cursar uma disciplina ("o que PRECISO fazer antes de X")
recommended_before  — o que é BOM/recomendado/útil fazer antes de uma disciplina (não é pré-requisito formal)
co_prerequisite     — disciplinas que compartilham os mesmos pré-requisitos / co-pré-requisitos
critical_disciplines — disciplinas mais importantes/críticas do currículo (mais dependentes, mais desbloqueiam)
dependents          — quais disciplinas dependem de / desbloqueiam outra
discipline_docentes — quem leciona uma disciplina
docente_info        — email, sala, contato de um docente
docente_areas       — áreas de pesquisa de um docente
docente_disciplines — quais disciplinas um docente leciona
docentes_by_area    — docentes por área de pesquisa
disciplinas_termo   — disciplinas de um termo (term: "N:CURSO")
todos_termos_curso  — grade completa de um curso
matriz_info         — informações gerais sobre um curso
eletivas_curso      — eletivas de um curso
coordenador_curso   — coordenador de um curso
listar_cursos       — listar cursos disponíveis
trajectory_planning — caminho/planejamento para chegar em uma disciplina
artigos_sobre       — artigos do regimento sobre um tema
faqs                — dúvidas frequentes

REGRAS:
- Para trajectory_planning, "term" é a disciplina ALVO e "completed" lista as já cursadas.
- "term" deve ser copiado da PERGUNTA. NUNCA invente um nome que não foi
  citado pelo usuário; se a pergunta não cita nenhuma entidade, use "term": "".
- Nomes de disciplinas podem conter ":" — nunca parta o nome pelo ":",
  preserve o nome completo em "term".

Pergunta: {question}

Responda APENAS com JSON válido, sem explicações:"""

    def __init__(self, embeddings_model=None, llm=None):
        """
        Inicializa o classificador.

        Args:
            embeddings_model: Modelo de embeddings (OllamaEmbeddings ou similar)
            llm: LLM (LangChain BaseLLM) para classificação quando embeddings falham
        """
        self.embeddings_model = embeddings_model
        self.llm = llm
        self._intent_embeddings: Dict[str, np.ndarray] = {}
        self._initialized = False

    def set_llm(self, llm) -> None:
        """Injeta o LLM após a construção (evita dependência circular)."""
        self.llm = llm
    
    def initialize(self):
        """Pré-computa embeddings dos exemplos de treinamento."""
        if self._initialized or not self.embeddings_model:
            return
        
        print("Inicializando classificador de intenção...")
        
        for intent, examples in self.INTENT_EXAMPLES.items():
            try:
                # Gerar embeddings para todos os exemplos
                embeddings = self.embeddings_model.embed_documents(examples)
                # Calcular centróide (média) dos embeddings
                self._intent_embeddings[intent] = np.mean(embeddings, axis=0)
            except Exception as e:
                print(f"  Erro ao processar {intent}: {e}")
        
        self._initialized = True
        print(f"  ✓ {len(self._intent_embeddings)} intenções carregadas")
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calcula similaridade de cosseno entre dois vetores."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def _quick_regex_check(self, question: str) -> Optional[str]:
        """Verifica padrões regex óbvios para boost de confiança."""
        question_lower = question.lower()
        for intent, pattern in self.QUICK_PATTERNS.items():
            if re.search(pattern, question_lower):
                return intent
        return None
    
    def _extract_term(self, question: str, intent: str) -> str:
        """Extrai o termo relevante da pergunta baseado na intenção."""
        question_lower = question.lower().strip()
        
        # Padrões específicos por intenção
        patterns = self.TERM_PATTERNS.get(intent, [])
        
        for pattern in patterns:
            match = re.search(pattern, question_lower, re.IGNORECASE)
            if match:
                # Pegar o último grupo capturado
                term = match.group(match.lastindex or 1).strip()
                # Limpar pontuação
                term = re.sub(r'[\?.,!]+$', '', term).strip()
                # Remover preposições finais
                term = re.sub(r'\s+(da|de|do|na|no|em)$', '', term, flags=re.IGNORECASE).strip()
                
                # Caso especial: disciplinas_termo retorna "numero:curso"
                if intent == 'disciplinas_termo' and match.lastindex == 2:
                    numero = match.group(1)
                    curso = match.group(2).strip()
                    curso = re.sub(r'[\?.,!]+$', '', curso).strip()
                    return f"{numero}:{curso}"

                # Caso especial: trajectory_planning com completed+target
                if intent == 'trajectory_planning' and match.lastindex == 2:
                    g1 = re.sub(r'[\?.,!]+$', '', match.group(1)).strip()
                    g2 = re.sub(r'[\?.,!]+$', '', match.group(2)).strip()
                    # "quero chegar em TARGET, já fiz COMPLETED" → grupos invertidos
                    if re.match(r'quero\s+chegar\s+em\b', question_lower):
                        return f"{g2}:{g1}"  # completed:target
                    return f"{g1}:{g2}"
                # Caso especial: "já fiz X, Y, como fica?" (completed sem target)
                if intent == 'trajectory_planning':
                    no_target = re.search(
                        r'(?:j[aá]\s+)?(?:fiz|conclui|conclu[ií])\s+(.+?)[,.]?\s+(?:como\s+fica|o\s+que\s+falta)\s*\??',
                        question_lower, re.IGNORECASE
                    )
                    if no_target:
                        completed = re.sub(r'[\?.,!]+$', '', no_target.group(1)).strip()
                        return f"{completed}:"
                
                if len(term) >= 2:
                    return term
        
        # Fallback: extrair substantivos da pergunta
        # Remover palavras comuns e pegar o que sobrar
        stopwords = {
            'qual', 'quais', 'quem', 'como', 'onde', 'quando', 'que', 'o', 'a', 'os', 'as',
            'de', 'da', 'do', 'em', 'na', 'no', 'para', 'por', 'com', 'são', 'é', 'tem',
            'professor', 'professora', 'professores', 'professoras',
            'docente', 'docentes', 'disciplina', 'matéria', 'curso',
            'leciona', 'lecionam', 'ensina', 'ensinam', 'dá', 'dão', 'aula',
            'pré-requisitos', 'requisitos',
            # Pronomes e determinantes que nunca são o nome de uma disciplina
            'ementa', 'ementas', 'ela', 'ele', 'elas', 'eles', 'dela', 'dele', 'delas', 'deles',
            'isso', 'esta', 'este', 'essa', 'esse', 'disso', 'nessa', 'nesse', 'nessa',
        }
        
        words = [re.sub(r'[?!.,;:]+$', '', w) for w in question_lower.split()]
        terms = [w for w in words if w not in stopwords and len(w) > 2]

        if terms:
            return ' '.join(terms[-3:])  # Últimas 3 palavras relevantes
        
        return ""
    
    def _llm_classify(self, question: str) -> Optional['ClassificationResult']:
        """Usa o LLM para classificar intent e extrair termo via JSON."""
        if not self.llm:
            return None
        import json
        try:
            prompt = self._LLM_PROMPT.format(question=question)
            raw = self.llm.invoke(prompt)
            text = raw.content if hasattr(raw, 'content') else str(raw)
            # Extrair JSON mesmo se o modelo adicionou texto extra
            json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if not json_match:
                return None
            data = json.loads(json_match.group())
            # `or ''`: o modelo pode devolver "intent"/"term": null (JSON) —
            # .strip() direto em None estourava e descartava a classificação
            intent = (data.get('intent') or '').strip()
            term = (data.get('term') or '').strip()
            completed = data.get('completed') or []
            if not intent:
                return None
            # Para trajectory_planning, montar "completed:target"
            if intent == 'trajectory_planning' and term:
                if completed:
                    term = f"{', '.join(completed)}:{term}"
            return ClassificationResult(
                intent=intent,
                term=term.lower(),
                confidence=0.9,
                method='llm',
            )
        except Exception as e:
            print(f"[IntentClassifier] Erro no LLM: {e}")
            return None

    def classify(self, question: str) -> ClassificationResult:
        """
        Classifica a intenção de uma pergunta.

        Ordem de prioridade:
        1. Regex rápido (QUICK_PATTERNS) — padrões explícitos, confiança máxima.
           Usa LLM apenas para extrair o termo, não para reclassificar.
        2. Embeddings semânticos — reconhece paráfrases.
           Usa LLM para confirmar/refinar (pode sobrescrever embeddings).
        3. LLM — classificação completa quando os anteriores não respondem.
        """
        question_lower = question.lower().strip()

        # 1. Regex explícito: alta precisão no INTENT — mas a extração do TERMO
        #    é LLM-first (o regex de termo produz lixo em frases fora do padrão;
        #    o LLM entende a frase inteira e o grounding no KG valida depois)
        quick_intent = self._quick_regex_check(question)
        if quick_intent:
            llm_result = self._llm_classify(question)
            if llm_result and llm_result.term:
                if llm_result.intent == quick_intent:
                    return llm_result  # LLM concordou por completo
                # Intent do regex (prior de alta precisão) + termo do LLM
                return ClassificationResult(
                    intent=quick_intent,
                    term=llm_result.term,
                    confidence=0.85,
                    method='regex+llm_term',
                )
            # Sem LLM disponível: fallback para extração por regex
            term = self._extract_term(question, quick_intent)
            return ClassificationResult(
                intent=quick_intent,
                term=term,
                confidence=0.85,
                method='regex',
            )

        # 2. Embeddings semânticos para paráfrases não cobertas pelo regex
        if self._initialized and self.embeddings_model:
            try:
                question_embedding = np.array(
                    self.embeddings_model.embed_query(question)
                )
                best_intent = None
                best_score = -1.0

                for intent, centroid in self._intent_embeddings.items():
                    similarity = self._cosine_similarity(question_embedding, centroid)
                    if similarity > best_score:
                        best_score = similarity
                        best_intent = intent

                if best_score >= 0.45:
                    # LLM pode sobrescrever embeddings (captura nuances como co_prerequisite)
                    llm_result = self._llm_classify(question)
                    if llm_result:
                        return llm_result
                    term = self._extract_term(question, best_intent)
                    return ClassificationResult(
                        intent=best_intent,
                        term=term,
                        confidence=best_score,
                        method='embeddings',
                    )

            except Exception as e:
                print(f"[IntentClassifier] Erro nos embeddings: {e}")

        # 3. LLM como classificador completo
        llm_result = self._llm_classify(question)
        if llm_result:
            return llm_result

        return ClassificationResult(
            intent='unknown',
            term='',
            confidence=0.0,
            method='none',
        )
    
    def classify_batch(self, questions: List[str]) -> List[ClassificationResult]:
        """Classifica múltiplas perguntas de uma vez."""
        return [self.classify(q) for q in questions]

