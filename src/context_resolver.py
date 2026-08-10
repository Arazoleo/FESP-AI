#!/usr/bin/env python3
"""
Context Resolver - Resolve referências contextuais em conversas.

Funcionalidades:
1. Context Tracker: Rastreia entidades ativas (curso, disciplina, docente)
2. Query Rewriter: Reescreve perguntas com contexto implícito
3. Coreference Resolution: Resolve pronomes (ela, dele, dessa, etc.)
4. LLM Query Rewriting: Usa LLM para casos complexos
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .atividades_complementares import (
    OFFER_MARKER as _AC_OFFER_MARKER,
    BREAKDOWN_CANONICAL_QUESTION as _AC_BREAKDOWN_QUESTION,
    is_affirmative_reply as _is_affirmative_reply,
)

logger = logging.getLogger(__name__)

# Cursos reconhecidos (siglas e nomes) — mesma alternância dos curso_patterns
_CURSO_ALT = (
    r'(?:bcc|bct|bbt|ec|engenharia\s+de\s+computa[cç][aã]o|'
    r'ci[eê]ncia\s+da\s+computa[cç][aã]o|ci[eê]ncia\s+e\s+tecnologia|'
    r'biotecnologia|biomedicina)'
)
# Mensagem que é SÓ uma referência de curso: "do BCT", "BCT", "de BCC",
# "no curso de biotecnologia" — típica resposta a um pedido de clarificação.
_COURSE_ONLY_RE = re.compile(
    rf'^(?:e\s+)?(?:(?:d[oae]s?|n[oa]s?|em|para\s+[oa]?)\s+)?'
    rf'(?:curso\s+(?:de\s+)?)?({_CURSO_ALT})\s*[?!.]*$',
    re.IGNORECASE,
)
# Qualquer menção a curso dentro de uma frase maior
_COURSE_MENTION_RE = re.compile(rf'\b{_CURSO_ALT}\b', re.IGNORECASE)
# A mensagem parece uma pergunta (para detectar a "pergunta pendente")
_QUESTION_CUE_RE = re.compile(
    r'\?|^(?:quais|qual|quanta?s?|quantos|quem|como|onde|quando|o\s+que|tem|existe)\b',
    re.IGNORECASE,
)


def _last_user_intent(history: List[dict]) -> Optional[str]:
    """Tenta detectar o intent da última pergunta do usuário a partir de keywords no texto."""
    for msg in reversed(history):
        if msg.get('role') != 'user':
            continue
        q = msg.get('content', '').lower()
        if re.search(r'pr[eé]-?requisitos?', q):
            return 'prerequisite_chain'
        if re.search(r'quem\s+leciona|quais?\s+(?:professore?s?|docentes?)', q):
            return 'discipline_docentes'
        if re.search(r'ementa', q):
            return 'ementa_disciplina'
        return None
    return None


# Template para reescrita de query com LLM
QUERY_REWRITE_TEMPLATE = """Você é um assistente que reescreve perguntas para torná-las auto-contidas.

Dado o contexto da conversa e a pergunta atual, reescreva a pergunta de forma completa, 
substituindo pronomes e referências implícitas pelos nomes reais.

CONTEXTO DA CONVERSA:
{history}

PERGUNTA ATUAL: {question}

ENTIDADES ATIVAS:
- Curso: {curso}
- Disciplina: {disciplina}
- Docente: {docente}

Reescreva a pergunta de forma completa e auto-contida. 
Se a pergunta já estiver completa, retorne-a sem modificações.
Responda APENAS com a pergunta reescrita, sem explicações.

PERGUNTA REESCRITA:"""


@dataclass
class ConversationContext:
    """Mantém o contexto ativo de uma conversa."""
    # Entidades ativas (última mencionada de cada tipo)
    curso: Optional[str] = None
    disciplina: Optional[str] = None
    docente: Optional[str] = None
    termo: Optional[str] = None

    # Lista de entidades mencionadas (para "qual deles?")
    docentes_list: List[str] = field(default_factory=list)
    disciplinas_list: List[str] = field(default_factory=list)

    # Oferta pendente do assistente (ex.: "quer o detalhamento por eixo?").
    # Setada/limpada a cada mensagem do assistente; um aceite curto do usuário
    # ("sim, pode") é reescrito para a pergunta canônica correspondente.
    pending_offer: Optional[str] = None

    # Proveniência (bug T8): True quando a disciplina ativa foi definida
    # EXPLICITAMENTE pelo usuário ("e sobre Banco de Dados?"). Enquanto True,
    # menções heurísticas em respostas do assistente ("...pré-requisito para
    # cursar Projetos em Engenharia de Computação") NÃO podem sobrescrevê-la —
    # nem no update do fim do turno, nem no replay do histórico feito pela API
    # a cada turno (que reprocessa a resposta antiga DEPOIS da troca do usuário).
    disciplina_from_user: bool = False

    def update_from_message(self, message: str, role: str = "user"):
        """Atualiza contexto baseado em uma mensagem."""
        message_lower = message.lower()

        # Ofertas de follow-up: só a ÚLTIMA mensagem do assistente conta —
        # uma resposta nova sem oferta limpa a pendência anterior.
        if role == "assistant":
            self.pending_offer = (
                "ac_breakdown" if _AC_OFFER_MARKER in message else None
            )

        # (T8) Troca explícita de entidade pelo usuário tem precedência:
        # mensagens do assistente não podem reverter a disciplina ativa.
        protect_disc = role == "assistant" and self.disciplina_from_user
        
        # Detectar curso mencionado
        curso_patterns = [
            r'\b(?:curso\s+(?:de\s+)?|matriz\s+(?:de\s+)?|grade\s+(?:de\s+)?)?'
            r'(bcc|bct|bbt|ec|engenharia\s+de\s+computa[cç][aã]o|'
            r'ci[eê]ncia\s+da\s+computa[cç][aã]o|ci[eê]ncia\s+e\s+tecnologia|'
            r'biotecnologia|biomedicina)\b',
        ]
        for pattern in curso_patterns:
            match = re.search(pattern, message_lower)
            if match:
                self.curso = match.group(1).upper() if len(match.group(1)) <= 3 else match.group(1).title()
                break
        
        # Detectar termo mencionado
        termo_match = re.search(r'termo\s+(\d+)', message_lower)
        if termo_match:
            self.termo = termo_match.group(1)
        
        # Detectar disciplina mencionada — pesquisar em message_lower mas extrair
        # da mensagem original para preservar capitalização (ex: "Cálculo Numérico")
        # Palavras/frases que indicam referência vaga e não devem ser aceitas como nome.
        _DISC_REJEITAR = frozenset({
            'o', 'a', 'os', 'as', 'que', 'qual', 'quais',
            'essa', 'esse', 'esta', 'este', 'essas', 'esses',
            'ela', 'ele', 'elas', 'eles', 'dela', 'dele',
            'isso', 'isto', 'aquilo', 'aquela', 'aquele',
            'essa disciplina', 'esta disciplina', 'essa matéria', 'esta matéria',
            'essa cadeira', 'esta cadeira',
        })
        disc_patterns = [
            # Já existentes
            r'disciplina\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'pr[eé]-?requisitos?\s+(?:de|da|do)\s+(.+?)(?:\?|,|\.|$)',
            r'quem\s+leciona\s+(.+?)(?:\?|$)',
            # "O que é X?" / "O que se estuda em X?"
            r'o\s+que\s+[eé]\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?(.+?)(?:\?|$)',
            r'o\s+que\s+(?:se\s+)?(?:estuda|aprende)\s+em\s+(.+?)(?:\?|$)',
            # "fale sobre X" / "me fale mais sobre X"
            r'(?:fale|fala|me\s+fale|me\s+fala)(?:\s+mais)?\s+sobre\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?(.+?)(?:\?|$)',
            # "o que sabe sobre X" / "sabe sobre X"
            r'(?:o\s+que\s+(?:vc|você\s+)?sabe|sabe)\s+sobre\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?(.+?)(?:\?|$)',
            # "ementa de X"
            r'ementa\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            # "descreva X" / "explique X"
            r'(?:descreva|explique|explica|me\s+explique)\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?(.+?)(?:\?|$)',
            # "quais professores dão X" → captura a disciplina como efeito colateral útil
            r'(?:professores?|docentes?)\s+(?:d[aã]o|leciona[m]?|ensina[m]?)\s+(.+?)(?:\?|$)',
        ]
        for pattern in disc_patterns:
            match = re.search(pattern, message_lower)
            if match:
                # Usar a posição do match para extrair o texto ORIGINAL (com capitalização)
                start, end = match.span(1)
                disc_name = message[start:end].strip()
                disc_name = re.sub(r'[,\.\?]+$', '', disc_name).strip()
                disc_name = re.sub(r'\s+(?:da|de|do|das|dos)\s*$', '', disc_name, flags=re.IGNORECASE).strip()
                disc_lower = disc_name.lower()
                # Rejeitar pronomes/demonstrativos e referências a docentes
                if disc_lower not in _DISC_REJEITAR and len(disc_name) >= 3:
                    if not re.search(r'\b(?:professor[a]?|docente)\b', disc_lower):
                        if not protect_disc:
                            self.disciplina = disc_name
                            if role == "user":
                                self.disciplina_from_user = True
                        break

        # Detectar padrão "E de X, ..." / "(e) sobre X" para mudança de disciplina
        mudanca_disc = re.search(r'^(?:e\s+(?:de|sobre)|sobre)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)', message, re.IGNORECASE)
        if mudanca_disc and not protect_disc:
            self.disciplina = mudanca_disc.group(1).strip()
            if role == "user":
                self.disciplina_from_user = True

        # Resposta de clarificação: mensagem é apenas um nome próprio (ex: "Banco de Dados")
        # → usuário está respondendo a "qual disciplina?"
        if (
            role == "user"
            and not self.disciplina  # só se não capturou pelos padrões acima
            and len(message.split()) <= 5
            and not re.search(r'[?!]', message)
            # Rejeitar se contém verbos/pronomes interrogativos ou palavras de ação
            and not re.search(r'\b(?:que|qual|quais|quem|como|onde|quando|sim|não|nao|é|sao|são|tem|tenho|quero|preciso)\b', message_lower)
            and re.match(r'^[A-ZÀ-Ú]', message)
        ):
            candidate = message.strip().rstrip('.,')
            # Referência de curso ("BCT", "Do BCT") NÃO é disciplina — é resposta
            # de clarificação de curso, tratada pelo ContextResolver.
            if len(candidate) >= 3 and not _COURSE_ONLY_RE.match(candidate):
                self.disciplina = candidate
                self.disciplina_from_user = True

        # Detectar disciplina em respostas do assistente
        if role == "assistant" and not protect_disc:
            # Sem re.IGNORECASE para exigir letra maiúscula — evita capturar verbos.
            verbos_comuns = {'cursar', 'lecionar', 'fazer', 'pegar', 'estudar', 'ter', 'para'}
            resp_disc_patterns = [
                r'(?:para\s+cursar|pr[eé]-requisitos?\s+(?:de|da))\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                r'[Aa]\s+disciplina\s+(?:de\s+)?([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                r'^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)\s+[eé]\s+uma\s+disciplina',
            ]
            for pattern in resp_disc_patterns:
                m = re.search(pattern, message, re.MULTILINE)
                if m:
                    disc = m.group(1).strip()
                    if disc.lower() not in verbos_comuns and len(disc) >= 3:
                        self.disciplina = disc
                        break
        
        # Detectar docente mencionado
        # Nome capitalizado "solto" só conta como docente com prefixo explícito
        # ("professor X" / "quem é X") — sem isso, qualquer nome próprio na
        # frase virava docente ("Matriz Curricular", "Estrutura de Dados") e os
        # pronomes "dele/dela" passavam a resolver para um falso docente.
        docente_patterns = [
            r'professor(?:a)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
            r'[Qq]uem\s+[eé]\s+(?:o\s+|a\s+)?([A-ZÀ-Ú][a-zà-ú]+\s+[A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)\??',
        ]
        for pattern in docente_patterns:
            match = re.search(pattern, message)
            if match:
                nome = match.group(1).strip()
                # Filtrar falsos positivos
                if nome.lower() not in ['me', 'fale', 'sobre', 'qual', 'quem', 'onde', 'como']:
                    self.docente = nome
                    break
        
        # Extrair listas de docentes de respostas do assistente
        if role == "assistant":
            # Pattern para lista "- Nome Sobrenome"
            docentes = re.findall(r'^-\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)', message, re.MULTILINE)
            if docentes:
                self.docentes_list = docentes
            
            # Pattern para disciplinas em resposta
            disciplinas = re.findall(r'^-\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[a-zà-ú]+)*)\s+\(', message, re.MULTILINE)
            if disciplinas:
                self.disciplinas_list = disciplinas


class ContextResolver:
    """Resolve referências contextuais em perguntas."""
    
    # Padrões de pronomes e referências
    # Palavras que sinalizam que a pergunta é inequivocamente sobre uma DISCIPLINA.
    # Quando presentes junto com um pronome, disciplina tem prioridade sobre docente.
    DISCIPLINE_PRIORITY_WORDS = frozenset({
        'ementa', 'ementas', 'conteúdo', 'conteudo', 'carga', 'horária', 'horaria',
        'bibliografia', 'tópicos', 'topicos', 'objetivos',
        'pré-requisito', 'pre-requisito', 'prerequisito',
        'pré-requisitos', 'pre-requisitos', 'prerequisitos',
    })

    PRONOME_PATTERNS = {
        'docente': [
            r'\b(?:dele|dela)\b',
            r'\b(?:desse|dessa)\s+(?:professor|professora|docente)\b',
            r'\b(?:sobre|com)\s+(?:ele|ela)\b',
            r'\b(?:email|sala|contato|[aá]reas?)\s+(?:dele|dela)\b',
            # "que ele/ela leciona/faz" e "disciplinas que ele"
            r'\bque\s+(?:ele|ela)\b',
            r'\b(?:ele|ela)\s+(?:leciona|ensina|ministra|pesquisa|atua|costuma)\b',
        ],
        'disciplina': [
            r'\b(?:essa|esta|desta|dessa)\s+(?:disciplina|mat[eé]ria|cadeira)\b',
            r'\bpr[eé]-?requisitos?\s+(?:dela|dessa)\b',
            r'\bquem\s+leciona\s+(?:ela|essa)\b',
            # Pronomes genéricos em contexto inequívoco de disciplina
            r'\bementa\s+(?:d[ae]la?|d[ae]le|d[ae]ss[ae]|dela)\b',
            r'\b(?:d[ae]la?|d[ae]le)\b(?=.*(?:ementa|conteúdo|conteudo|carga|bibliograf))',
        ],
        'curso': [
            r'\b(?:desse|dessa|deste|desta)\s+(?:curso|gradua[cç][aã]o)\b',
            r'\bcoordenador(?:a)?\s+(?:desse|dessa|dele|dela)\b',
            r'\b(?:e\s+)?(?:no|do)\s+termo\s+\d+\b',  # "E no termo 6?" implica curso anterior
        ],
    }
    
    # Padrões de perguntas de follow-up curtas
    FOLLOWUP_PATTERNS = [
        r'^e\s+(?:as?|os?|no|na|do|da)\s+',       # "E as do termo 5?"
        r'^(?:e\s+)?qual\s+(?:deles|delas)\b',     # "Qual deles trabalha com..."
        r'^(?:e\s+)?quais?\s+(?:s[aã]o)?\s*\?',   # "E quais são?"
        # "e sobre X?" / "sobre X?" — troca de entidade sem verbo
        r'^(?:e\s+)?sobre\s+\w',
        # "e de X?" / "e do X?" — muda entidade mantendo o tipo de consulta anterior
        r'^e\s+(?:de|do|da)\s+\w',
        # Intent-switch follow-ups — só disparam quando NÃO há entidade explícita na pergunta
        # (ancorados no fim: "e os pré-requisitos?" sim, "pré-requisitos de IHC?" não)
        r'^(?:(?:e|qual|quais|tem)\s+)?(?:os?\s+|as?\s+)?pr[eé]-?requisitos?\s*\??\s*$',
        r'^(?:(?:e|qual|quais)\s+)?(?:quem\s+(?:leciona|d[aá]|ensina)|os?\s+docentes?|os?\s+professores?)\s*\??\s*$',
        r'^(?:tem|qual|e)[\s\w]{0,6}ementa\s*\??\s*$',
        r'^(?:(?:e|qual)\s+)?(?:a\s+)?carga\s+hor[aá]ria\s*\??\s*$',
        r'^(?:(?:e|qual)\s+)?(?:a\s+)?bibliograf\w*\s*\??\s*$',
        r'^(?:(?:e|quais)\s+)?(?:as?\s+)?eletivas?\s*\??\s*$',
        r'^(?:(?:e|quem)\s+)?(?:[eé]\s+)?(?:o\s+)?coordenador\s*\??\s*$',
        # Anáforas no meio da frase: "tem como saber algumas dessas eletivas?",
        # "e a matriz dele?" — herdam o curso do contexto
        r'\bdess[ae]s?\s+(?:eletivas?|optativas?)\b',
        r'\bess[ae]s\s+eletivas?\b',
        r'\b(?:a\s+)?(?:matriz|grade)\s+(?:dele|dela|desse|dessa)\b',
        # "quais as disciplinas que tenho que fazer?" após falar de um curso
        r'\bquais?\s+(?:as\s+)?disciplinas?\s+(?:que\s+)?(?:eu\s+)?(?:tenho|preciso|devo)\s+(?:que\s+)?(?:fazer|cursar)\b',
        # Quebra/distribuição de horas — herda o curso do contexto (T2):
        # "essas horas estão distribuídas...?", "quantas horas de eletivas?"
        r'\bhoras?\b.*\b(?:distribu[ií]d|dividid)',
        r'\b(?:distribu[ií]d|dividid)\w*\b.*\bhoras?\b',
        r'^(?:e\s+)?(?:quantas\s+)?horas\s+de\s+\w+(?:\s+\w+)?\s*\??\s*$',
    ]

    # Mapeamento: padrão → (template_disciplina, template_curso)
    _INTENT_FOLLOWUP: list = [
        (
            [r'pr[eé]-?requisitos?'],
            "Quais os pré-requisitos de {disciplina}?",
            None,
        ),
        (
            [r'quem\s+(?:leciona|d[aá]|ensina)', r'docentes?', r'professores?'],
            "Quem leciona {disciplina}?",
            None,
        ),
        (
            [r'ementa'],
            "Qual a ementa de {disciplina}?",
            None,
        ),
        (
            [r'carga\s+hor[aá]ria', r'quantas\s+horas'],
            "Qual a carga horária de {disciplina}?",
            None,
        ),
        (
            [r'bibliograf'],
            "Qual a bibliografia de {disciplina}?",
            None,
        ),
        (
            [r'eletivas?', r'optativas?'],
            None,
            "Quais as eletivas de {curso}?",
        ),
        (
            [r'coordenador'],
            None,
            "Quem é o coordenador de {curso}?",
        ),
        (
            [r'matriz', r'grade'],
            None,
            "Como funciona a matriz curricular de {curso}?",
        ),
        (
            [r'disciplinas?\s+(?:que\s+)?(?:eu\s+)?(?:tenho|preciso|devo)\s+(?:que\s+)?(?:fazer|cursar)'],
            None,
            "Quais as disciplinas de {curso}?",
        ),
    ]
    
    def __init__(self):
        self.contexts: Dict[str, ConversationContext] = {}
    
    def get_context(self, conversation_id: str) -> ConversationContext:
        """Obtém ou cria contexto para uma conversa."""
        if conversation_id not in self.contexts:
            self.contexts[conversation_id] = ConversationContext()
        return self.contexts[conversation_id]
    
    def update_context(self, conversation_id: str, message: str, role: str = "user"):
        """Atualiza contexto com nova mensagem."""
        context = self.get_context(conversation_id)
        context.update_from_message(message, role)
    
    def resolve_question(
        self, 
        question: str, 
        conversation_id: str,
        history: Optional[List[dict]] = None
    ) -> Tuple[str, bool]:
        """
        Resolve referências contextuais na pergunta.
        
        Returns:
            Tuple[str, bool]: (pergunta resolvida, foi modificada)
        """
        context = self.get_context(conversation_id)
        original = question
        resolved = question
        modified = False
        
        question_lower = question.lower()

        # 0-pre. Aceite de oferta pendente: a última resposta do assistente
        # ofereceu o detalhamento por eixo das atividades complementares e o
        # usuário aceitou com uma mensagem curta ("sim", "pode, por favor") →
        # reescrever para a pergunta canônica, que toma o atalho simbólico.
        if context.pending_offer == "ac_breakdown" and _is_affirmative_reply(question):
            context.pending_offer = None
            resolved = _AC_BREAKDOWN_QUESTION
            logger.info(
                f"[CONTEXT][oferta-ac] aceite '{question}' → '{resolved}'"
            )
            return resolved, True

        # 0. Se a pergunta menciona explicitamente um nome próprio com "com a/o X",
        #    atualizar context.docente ANTES de resolver pronomes.
        #    Isso evita substituir "dela" pelo docente errado do contexto.
        explicit_match = re.search(
            r'(?:com\s+(?:o|a)\s+)([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)',
            question
        )
        if explicit_match:
            context.docente = explicit_match.group(1)

        # 0b. "Email/sala/contato do Rodrigo" → resolver usando docentes_list para evitar
        #     ambiguidade (ex.: Martin Rodrigo vs Rodrigo Colnago). Escolher o docente da
        #     lista cujo primeiro nome coincide.
        if not modified and context.docentes_list:
            partial_match = re.search(
                r'\b(?:email|e-?mail|sala|contato)\s+(?:de|do|da)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                question,
                re.IGNORECASE
            )
            if partial_match:
                partial_name = partial_match.group(1).strip()
                full_name = self._resolve_partial_docente_from_list(partial_name, context.docentes_list)
                if full_name:
                    context.docente = full_name
                    # Reescrever "do Rodrigo" / "da Maria" → "do professor Nome Completo"
                    resolved = re.sub(
                        r'\b(do|da)\s+' + re.escape(partial_name) + r'\b',
                        f'\\1 professor {full_name}',
                        resolved,
                        count=1,
                        flags=re.IGNORECASE
                    )
                    modified = True

        # 0c. Herança de clarificação (bug T3): a mensagem é SÓ uma referência
        #     de curso ("do BCT", "BCT") e a última pergunta do usuário no
        #     histórico era uma pergunta SEM curso (clarificação implícita) →
        #     combinar: pergunta pendente + curso.
        #     Ex.: "Quantas horas de eletivas?" + "do BCT"
        #          → "Quantas horas de eletivas do BCT?"
        if not modified and history:
            course_only = _COURSE_ONLY_RE.match(question.strip())
            if course_only:
                pending = self._find_pending_question_sem_curso(history)
                if pending:
                    base = re.sub(r'[\s?!.]+$', '', pending).strip()
                    ref = re.sub(r'^e\s+', '', question.strip(), flags=re.IGNORECASE)
                    ref = re.sub(r'[\s?!.]+$', '', ref).strip()
                    # "BCT" sozinho vira "do BCT"; "de BCC"/"no BCT" ficam como estão
                    if not re.match(r'^(?:d[oae]s?|n[oa]s?|em|para)\b', ref, re.IGNORECASE):
                        ref = f'do {ref}'
                    resolved = f'{base} {ref}?'
                    curso_raw = course_only.group(1)
                    context.curso = (
                        curso_raw.upper() if len(curso_raw) <= 3 else curso_raw.title()
                    )
                    modified = True
                    logger.info(
                        f"[CONTEXT][clarificacao-curso] '{question}' + pendente "
                        f"'{pending}' → '{resolved}'"
                    )

        # 1. Resolver referências a docentes (dele, dela, etc.)
        # EXCETO quando a pergunta contém palavras inequívocas de disciplina (ementa, conteúdo…)
        # — nesse caso pulamos para o passo 2 para evitar reescrever "ementa dela" como docente.
        has_discipline_priority = any(
            w in question_lower for w in self.DISCIPLINE_PRIORITY_WORDS
        )
        if not has_discipline_priority:
            for pattern in self.PRONOME_PATTERNS['docente']:
                if re.search(pattern, question_lower):
                    if context.docente:
                        resolved = self._replace_docente_reference(resolved, context.docente)
                        modified = True
                        break
                    # Tentar extrair do histórico
                    elif history:
                        docente = self._find_docente_in_history(history)
                        if docente:
                            context.docente = docente
                            resolved = self._replace_docente_reference(resolved, docente)
                            modified = True
                            break

        # 2. Resolver referências a disciplinas (dessa disciplina, etc.)
        if not modified:
            for pattern in self.PRONOME_PATTERNS['disciplina']:
                if re.search(pattern, question_lower):
                    if context.disciplina:
                        resolved = self._replace_disciplina_reference(resolved, context.disciplina)
                        modified = True
                        break
                    elif history:
                        disciplina = self._find_disciplina_in_history(history)
                        if disciplina:
                            context.disciplina = disciplina
                            resolved = self._replace_disciplina_reference(resolved, disciplina)
                            modified = True
                            break
        
        # 3. Resolver referências a cursos (desse curso, no termo X)
        if not modified:
            for pattern in self.PRONOME_PATTERNS['curso']:
                if re.search(pattern, question_lower):
                    if context.curso:
                        resolved = self._replace_curso_reference(resolved, context.curso)
                        modified = True
                        break
        
        # 4. Expandir perguntas de follow-up curtas
        if not modified and history:
            for pattern in self.FOLLOWUP_PATTERNS:
                if re.search(pattern, question_lower):
                    expanded = self._expand_followup(question, history, context)
                    if expanded != question:
                        resolved = expanded
                        modified = True
                        break
        
        # 5. Resolver "qual deles/delas"
        if not modified and re.search(r'\bqual\s+(?:deles|delas)\b', question_lower):
            if context.docentes_list:
                # Manter a pergunta mas adicionar contexto
                resolved = f"{question} (referindo-se a: {', '.join(context.docentes_list[:3])})"
                modified = True
        
        # 6. Resolver referências ordinais ("o primeiro", "do segundo", etc.)
        if not modified:
            ordinal_match = re.search(
                r'(?:do|da|o|a)\s*(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|[úu]ltim[oa])',
                question_lower
            )
            if ordinal_match:
                ordinal = ordinal_match.group(1)
                
                # Mapear ordinal para índice
                ordinal_map = {
                    'primeiro': 0, 'primeira': 0,
                    'segundo': 1, 'segunda': 1,
                    'terceiro': 2, 'terceira': 2,
                    'quarto': 3, 'quarta': 3,
                    'quinto': 4, 'quinta': 4,
                    'ultimo': -1, 'última': -1, 'ultim': -1,
                }
                
                # Normalizar ordinal
                ordinal_key = ordinal.replace('ú', 'u').replace('a', 'o')
                if ordinal_key.endswith('o'):
                    ordinal_key = ordinal_key[:-1] + 'o'
                
                idx = None
                for key, val in ordinal_map.items():
                    if key in ordinal:
                        idx = val
                        break
                
                if idx is not None:
                    # Verificar se temos lista de docentes
                    if context.docentes_list:
                        try:
                            docente = context.docentes_list[idx]
                            # Substituir referência ordinal pelo nome
                            resolved = re.sub(
                                r'(?:do|da|o|a)\s*(?:primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|[úu]ltim[oa])',
                                f'do professor {docente}',
                                question,
                                flags=re.IGNORECASE
                            )
                            context.docente = docente  # Atualizar contexto
                            modified = True
                        except IndexError:
                            pass
                    # Ou lista de disciplinas
                    elif context.disciplinas_list:
                        try:
                            disciplina = context.disciplinas_list[idx]
                            resolved = re.sub(
                                r'(?:do|da|o|a)\s*(?:primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|[úu]ltim[oa])',
                                f'de {disciplina}',
                                question,
                                flags=re.IGNORECASE
                            )
                            context.disciplina = disciplina
                            modified = True
                        except IndexError:
                            pass
        
        if modified:
            logger.info(f"[CONTEXT] Resolvido: '{original}' → '{resolved}'")
        
        return resolved, modified
    
    def _find_pending_question_sem_curso(self, history: List[dict]) -> Optional[str]:
        """
        Última pergunta do usuário no histórico que pedia algo mas NÃO citava
        curso — a "pergunta pendente" de uma clarificação implícita.
        Retorna None se a última pergunta já tinha curso ou não era pergunta.
        """
        for msg in reversed(history):
            if msg.get('role') != 'user':
                continue
            q = (msg.get('content') or '').strip()
            if not q or _COURSE_ONLY_RE.match(q):
                # respostas de clarificação anteriores não são a pergunta pendente
                continue
            if _COURSE_MENTION_RE.search(q):
                return None  # a última pergunta já tinha curso — nada a herdar
            if not _QUESTION_CUE_RE.search(q):
                return None
            return q
        return None

    def _resolve_partial_docente_from_list(self, partial_name: str, docentes_list: List[str]) -> Optional[str]:
        """
        Dado um nome parcial (ex. "Rodrigo") e a lista de docentes da última resposta,
        retorna o nome completo do docente cujo primeiro nome coincide.
        Evita que "Rodrigo" pegue "Martin Rodrigo Alejandro..." em vez de "Rodrigo Colnago Contreras".
        """
        if not partial_name or not docentes_list:
            return None
        partial_first = partial_name.split()[0].lower() if partial_name else ""
        matches = [
            full for full in docentes_list
            if full.strip() and full.split()[0].lower() == partial_first
        ]
        if len(matches) == 1:
            return matches[0].strip()
        if len(matches) > 1:
            # Várias pessoas com o mesmo primeiro nome: preferir a que bate com o nome parcial completo
            partial_lower = partial_name.lower()
            for full in matches:
                if full.lower().startswith(partial_lower) or partial_lower in full.lower().split():
                    return full.strip()
            return matches[0].strip()  # fallback: primeira da lista
        return None

    def _replace_docente_reference(self, question: str, docente: str) -> str:
        """Substitui referências pronominais por nome do docente."""
        replacements = [
            (r'\b(?:dele|dela)\b', f'do professor {docente}'),
            (r'\b(?:desse|dessa)\s+(?:professor|professora|docente)\b', f'do professor {docente}'),
            (r'\bcom\s+(?:ele|ela)\b', f'com o professor {docente}'),
            (r'\bsobre\s+(?:ele|ela)\b', f'sobre o professor {docente}'),
            # "que ele leciona" → "que {docente} leciona"
            (r'\bque\s+(?:ele|ela)\b', f'que {docente}'),
            # "ele costuma lecionar" → "{docente} leciona"
            (r'\b(?:ele|ela)\s+(?=leciona|ensina|ministra|pesquisa|atua|costuma)', f'{docente} '),
        ]
        result = question
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
    
    def _replace_disciplina_reference(self, question: str, disciplina: str) -> str:
        """Substitui referências a disciplina pelo nome."""
        result = question
        # "ementa dela/dessa" → "ementa de <disciplina>"
        result = re.sub(
            r'\bementa\s+(?:dela?|dele|dess[ae])\b',
            f'ementa de {disciplina}',
            result, flags=re.IGNORECASE,
        )
        # "(ementa|conteúdo|carga|bibliograf) dela/dessa" — captura prefixo + pronome
        result = re.sub(
            r'((?:ementa|conte[uú]do|carga|bibliograf)\s+)(?:dela?|dele|dess[ae])\b',
            lambda m: m.group(1) + f'de {disciplina}',
            result, flags=re.IGNORECASE,
        )
        # "dessa/desta disciplina/matéria/cadeira"
        result = re.sub(
            r'\b(?:essa|esta|desta|dessa)\s+(?:disciplina|mat[eé]ria|cadeira)\b',
            disciplina,
            result, flags=re.IGNORECASE,
        )
        # "dela/dessa" com lookahead de pré-requisito ou "quem leciona"
        result = re.sub(
            r'\b(?:dela|dessa)\b(?=.*(?:pr[eé]-?requisito|quem\s+leciona))',
            f'de {disciplina}',
            result, flags=re.IGNORECASE,
        )
        # Genérico: "dela" quando nenhum dos anteriores pegou
        result = re.sub(r'\bdela\b', f'de {disciplina}', result, flags=re.IGNORECASE)
        return result
    
    def _replace_curso_reference(self, question: str, curso: str) -> str:
        """Substitui referências a curso pelo nome."""
        question_lower = question.lower()
        
        # "E no termo 6?" → "Quais disciplinas do termo 6 de BCC?"
        if re.search(r'^e\s+(?:no|do)\s+termo\s+\d+', question_lower):
            termo = re.search(r'termo\s+(\d+)', question_lower).group(1)
            return f"Quais disciplinas do termo {termo} de {curso}?"
        
        # "desse curso" → "de BCC"
        replacements = [
            (r'\b(?:desse|dessa|deste|desta)\s+(?:curso|gradua[cç][aã]o)\b', f'de {curso}'),
            (r'\bcoordenador(?:a)?\s+(?:desse|dessa|dele|dela)\b', f'coordenador de {curso}'),
        ]
        result = question
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
    
    def _expand_followup(
        self,
        question: str,
        history: List[dict],
        context: ConversationContext,
    ) -> str:
        """Expande pergunta de follow-up curta, herdando entidade do contexto."""
        question_lower = question.lower()

        # "E no termo 6?" com curso no contexto
        termo_match = re.search(r'termo\s+(\d+)', question_lower)
        if termo_match and context.curso:
            novo_termo = termo_match.group(1)
            return f"Quais disciplinas do termo {novo_termo} de {context.curso}?"

        # Substituir termo numérico na última pergunta do usuário
        if termo_match:
            for msg in reversed(history):
                if msg['role'] == 'user':
                    last_question = msg['content']
                    if re.search(r'termo\s+\d+', last_question, re.IGNORECASE):
                        return re.sub(
                            r'termo\s+\d+',
                            f'termo {termo_match.group(1)}',
                            last_question,
                            flags=re.IGNORECASE,
                        )
                    break

        # "e sobre X?" / "sobre X?" — reescreve para "Me fale sobre X" e troca entidade
        sobre_match = re.match(r'^(?:e\s+)?sobre\s+(.+)', question_lower)
        if sobre_match:
            entity_lower = sobre_match.group(1).rstrip('?').strip()
            # Preservar capitalização original
            orig_match = re.match(r'^(?:e\s+)?sobre\s+(.+)', question, re.IGNORECASE)
            entity = orig_match.group(1).rstrip('?').strip() if orig_match else entity_lower.title()
            context.disciplina = entity
            context.disciplina_from_user = True
            rewritten = f"Me fale sobre {entity}"
            logger.info(f"[CONTEXT][sobre] '{question}' → '{rewritten}'")
            return rewritten

        # "e de X?" / "e do X?" — repete a pergunta anterior substituindo a entidade
        e_de_match = re.match(r'^e\s+(?:de|do|da)\s+(.+)', question_lower)
        if e_de_match:
            entity_raw = e_de_match.group(1).rstrip('?').strip()
            orig_match = re.match(r'^e\s+(?:de|do|da)\s+(.+)', question, re.IGNORECASE)
            entity = orig_match.group(1).rstrip('?').strip() if orig_match else entity_raw.title()
            # Descobrir qual era o último intent do usuário para remontar a pergunta
            last_intent = _last_user_intent(history)
            if last_intent == 'prerequisite_chain':
                rewritten = f"Quais os pré-requisitos de {entity}?"
            elif last_intent in ('discipline_docentes', 'docente_disciplines'):
                rewritten = f"Quem leciona {entity}?"
            elif last_intent == 'ementa_disciplina':
                rewritten = f"Qual a ementa de {entity}?"
            else:
                rewritten = f"Me fale sobre {entity}"
            context.disciplina = entity
            context.disciplina_from_user = True
            logger.info(f"[CONTEXT][e_de] '{question}' → '{rewritten}'")
            return rewritten

        # Quebra/distribuição de horas (T2): herda o curso do contexto.
        # "mas essas horas estão distribuídas em diferentes atividades?" após
        # falar do BCT → pergunta auto-contida sobre a distribuição das horas.
        if context.curso and not _COURSE_MENTION_RE.search(question):
            if re.search(r'\bhoras?\b.*\b(?:distribu[ií]d|dividid)', question_lower) or \
                    re.search(r'\b(?:distribu[ií]d|dividid)\w*\b.*\bhoras?\b', question_lower):
                # Redação alinhada à FAQ de integralização da página do curso
                # (quebra: UCs + extensão + complementares); evitar "carga
                # horária", que é frase de exclusão do agente do site.
                rewritten = (
                    f"Como as horas para integralizar o {context.curso} estão "
                    f"distribuídas entre unidades curriculares, extensão e "
                    f"atividades complementares?"
                )
                logger.info(f"[CONTEXT][horas-curso] '{question}' → '{rewritten}'")
                return rewritten
            horas_de = re.search(
                r'\bhoras\s+(?:de\s+|em\s+)?'
                r'(eletivas?|optativas?|extens[aã]o|(?:atividades\s+)?complementares|'
                r'(?:disciplinas\s+|ucs?\s+)?obrigat[oó]rias?)\b',
                question_lower,
            )
            if horas_de:
                rewritten = f"Quantas horas de {horas_de.group(1)} do {context.curso}?"
                logger.info(f"[CONTEXT][horas-curso] '{question}' → '{rewritten}'")
                return rewritten

        # Intent-switch follow-ups: detectar qual informação o usuário quer
        # e montar uma pergunta completa com a entidade do contexto.
        for patterns, tmpl_disc, tmpl_curso in self._INTENT_FOLLOWUP:
            if any(re.search(p, question_lower) for p in patterns):
                if tmpl_disc and context.disciplina:
                    rewritten = tmpl_disc.format(disciplina=context.disciplina)
                    logger.info(
                        f"[CONTEXT][followup-intent] '{question}' → '{rewritten}'"
                    )
                    return rewritten
                if tmpl_curso and context.curso:
                    rewritten = tmpl_curso.format(curso=context.curso)
                    logger.info(
                        f"[CONTEXT][followup-intent] '{question}' → '{rewritten}'"
                    )
                    return rewritten

        return question
    
    def _find_docente_in_history(self, history: List[dict]) -> Optional[str]:
        """Encontra nome de docente mencionado no histórico."""
        for msg in reversed(history):
            content = msg['content']
            
            # Na pergunta do usuário
            if msg['role'] == 'user':
                match = re.search(
                    r'(?:professor(?:a)?\s+|com\s+o\s+|com\s+a\s+|quem\s+[eé]\s+)'
                    r'([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)',
                    content
                )
                if match:
                    return match.group(1)
            
            # Na resposta do assistente
            elif msg['role'] == 'assistant':
                # "X é especialista" ou "O professor X"
                patterns = [
                    r'^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)\s+(?:[eé]\s+especialista|leciona)',
                    r'[Pp]rofessor(?:a)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                    r'^-\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.MULTILINE)
                    if match:
                        nome = match.group(1)
                        # Filtrar falsos positivos
                        if nome.lower() not in ['total', 'termo', 'matriz', 'disciplina']:
                            return nome
        
        return None
    
    def _find_disciplina_in_history(self, history: List[dict]) -> Optional[str]:
        """Encontra nome de disciplina mencionado no histórico."""
        for msg in reversed(history):
            content = msg['content']
            
            # Primeiro verificar respostas do assistente (mais confiável)
            if msg['role'] == 'assistant':
                # Sem re.IGNORECASE: exige letra maiúscula para evitar capturar verbos
                resp_patterns = [
                    r'(?:para\s+cursar|pr[eé]-requisitos?\s+(?:de|da))\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                    r'[Dd]ocentes?\s+(?:que\s+lecionam?|de)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                    # "X é uma disciplina..." — nome no início da frase
                    r'^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)\s+[eé]\s+uma\s+disciplina',
                    # "a disciplina de X" / "disciplina X"
                    r'[Aa]\s+disciplina\s+(?:de\s+)?([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                ]
                verbos_comuns = {'cursar', 'lecionar', 'fazer', 'pegar', 'estudar', 'ter', 'para'}
                for pattern in resp_patterns:
                    match = re.search(pattern, content, re.MULTILINE)
                    if match:
                        disc = match.group(1).strip()
                        disc_lower = disc.lower()
                        if disc_lower not in ['o', 'a', 'os', 'as', 'que', 'qual', 'quais', 'total'] \
                                and disc_lower not in verbos_comuns \
                                and len(disc) >= 3:
                            return disc
            
            # Depois verificar perguntas do usuário
            elif msg['role'] == 'user':
                _HIST_REJEITAR = frozenset({
                    'o', 'a', 'os', 'as', 'que', 'qual', 'quais',
                    'essa', 'esse', 'esta', 'este', 'ela', 'ele',
                    'dela', 'dele', 'isso', 'aquilo',
                    'essa disciplina', 'esta disciplina',
                })
                patterns = [
                    r'disciplina\s+(?:de\s+)?([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
                    r'pr[eé]-?requisitos?\s+(?:de|da|do|para)\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|,|\.|$)',
                    r'quem\s+leciona\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
                    r'o\s+que\s+[eé]\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
                    r'(?:fale|me\s+fale)(?:\s+mais)?\s+sobre\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
                    r'(?:o\s+que\s+(?:vc\s+)?sabe|sabe)\s+sobre\s+(?:a\s+(?:disciplina\s+(?:de\s+)?)?)?([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
                    r'ementa\s+(?:de|da|do)\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        disc = match.group(1).strip()
                        disc = re.sub(r'[\?.,!]+$', '', disc).strip()
                        disc = re.sub(r'\s+(?:da|de|do)\s*$', '', disc, flags=re.IGNORECASE).strip()
                        disc_lower = disc.lower()
                        if disc_lower not in _HIST_REJEITAR and len(disc) >= 3:
                            if not re.search(r'\b(?:professor[a]?|docente)\b', disc_lower):
                                return disc
        
        return None
    
    def clear_context(self, conversation_id: str):
        """Limpa contexto de uma conversa."""
        if conversation_id in self.contexts:
            del self.contexts[conversation_id]
    
    def rewrite_with_llm(
        self,
        question: str,
        conversation_id: str,
        history: List[dict],
        llm: Any
    ) -> str:
        """
        Usa LLM para reescrever pergunta ambígua.
        
        Só é chamado quando a resolução baseada em regras falha
        e a pergunta parece incompleta.
        """
        if not llm:
            return question
        
        context = self.get_context(conversation_id)
        
        # Formatar histórico
        history_text = ""
        for msg in history[-6:]:  # Últimas 6 mensagens
            role = "Usuário" if msg['role'] == 'user' else "Assistente"
            history_text += f"{role}: {msg['content'][:200]}\n"
        
        # Criar prompt
        prompt = QUERY_REWRITE_TEMPLATE.format(
            history=history_text or "Nenhum histórico",
            question=question,
            curso=context.curso or "Não especificado",
            disciplina=context.disciplina or "Não especificado",
            docente=context.docente or "Não especificado"
        )
        
        try:
            # Invocar LLM. Chat models retornam AIMessage (.content), não str —
            # o .strip() direto quebrava silenciosamente e a reescrita nunca rodava.
            response = llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            rewritten = text.strip().strip('"').strip()
            # Só a primeira linha útil (modelos às vezes adicionam explicação)
            rewritten = rewritten.splitlines()[0].strip() if rewritten else ""

            # Validar resposta
            if rewritten and 5 < len(rewritten) < 500:
                logger.info(f"[LLM REWRITE] '{question}' → '{rewritten}'")
                if rewritten.strip() != question.strip():
                    try:
                        from .telemetry import incr
                        incr("llm_rewrite")
                    except ImportError:
                        pass
                return rewritten
        except Exception as e:
            logger.warning(f"[LLM REWRITE] Falha: {e}")

        return question
    
    def is_ambiguous_question(self, question: str) -> bool:
        """Detecta se uma pergunta é ambígua e precisa de contexto."""
        question_lower = question.lower()
        
        # Se a pergunta começa com "E de/sobre X" onde X é uma entidade específica,
        # NÃO é ambígua - o usuário está mudando de assunto
        if re.search(r'^e\s+(?:de|sobre)\s+[A-Za-zÀ-ú]+', question_lower):
            # A pergunta menciona uma nova entidade, não precisa de contexto antigo
            return False
        
        # Se a pergunta menciona uma entidade específica (nome próprio), não é ambígua
        if re.search(r'(?:de|sobre|para)\s+[A-Z][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)?(?:\?|,|\s+quais?)', question):
            return False

        # Se contém sigla (2+ letras maiúsculas), a entidade é explícita — não é ambígua
        if re.search(r'\b[A-Z]{2,}\b', question):
            return False

        # Perguntas muito curtas são potencialmente ambíguas
        if len(question.split()) < 4:
            return True
        
        # Perguntas com pronomes não resolvidos
        ambiguous_patterns = [
            r'\b(?:ele|ela|eles|elas)\b',
            r'\b(?:isso|isto|aquilo)\b',
            r'\b(?:esse|essa|esses|essas)\s+(?!de\s)',  # "essa" mas não "essa de"
            r'\b(?:qual|quais)\s+(?:deles|delas)\b',
            # Pronomes oblíquos — "dela/dele" são os mais comuns em perguntas de follow-up
            # Ex.: "Tem a ementa dela?", "Qual o email dele?", "Quais as áreas delas?"
            r'\b(?:dela|dele|delas|deles)\b',
            # Demonstrativos contraídos: "dessas eletivas", "nesse curso", "daquela matéria"
            r'\b(?:dess[ae]s?|ness[ae]s?|daquel[ea]s?|naquel[ea]s?)\b',
            r'\bnel[ea]s?\b',
            # Continuação explícita: "E quais as disciplinas...?" — o "E" inicial
            # indica que a pergunta emenda no assunto anterior
            r'^\s*e\s+\w',
        ]

        for pattern in ambiguous_patterns:
            if re.search(pattern, question_lower):
                return True

        return False


# Instância global para uso na API
context_resolver = ContextResolver()

