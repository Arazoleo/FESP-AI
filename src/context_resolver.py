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

logger = logging.getLogger(__name__)


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
    
    def update_from_message(self, message: str, role: str = "user"):
        """Atualiza contexto baseado em uma mensagem."""
        message_lower = message.lower()
        
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
        
        # Detectar disciplina mencionada
        disc_patterns = [
            r'disciplina\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'pr[eé]-?requisitos?\s+(?:de|da|do)\s+(.+?)(?:\?|,|\.|$)',
            r'quem\s+leciona\s+(.+?)(?:\?|$)',
            r'(?:e\s+(?:de|sobre)\s+)?([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*),?\s+(?:quais?\s+)?(?:s[aã]o\s+)?(?:os?\s+)?pr[eé]-?requisitos?',
        ]
        for pattern in disc_patterns:
            match = re.search(pattern, message_lower)
            if match:
                disc_name = match.group(1).strip()
                # Limpar pontuação e palavras comuns
                disc_name = re.sub(r'[,\.\?]$', '', disc_name).strip()
                if disc_name.lower() not in ['o', 'a', 'os', 'as', 'que', 'qual', 'quais', 'essa', 'esse']:
                    self.disciplina = disc_name
                    break
        
        # Detectar padrão "E de X, ..." para mudança de disciplina
        mudanca_disc = re.search(r'^e\s+(?:de|sobre)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)', message, re.IGNORECASE)
        if mudanca_disc:
            self.disciplina = mudanca_disc.group(1).strip()
        
        # Detectar disciplina em respostas do assistente sobre pré-requisitos
        if role == "assistant":
            # "Para cursar X, são necessários..." ou "Os pré-requisitos de X são..."
            resp_disc_match = re.search(r'(?:para\s+cursar|pr[eé]-requisitos?\s+(?:de|da|para))\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)', message, re.IGNORECASE)
            if resp_disc_match:
                self.disciplina = resp_disc_match.group(1).strip()
        
        # Detectar docente mencionado
        docente_patterns = [
            r'professor(?:a)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
            r'(?:quem\s+[eé]\s+)?([A-ZÀ-Ú][a-zà-ú]+\s+[A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)\??',
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
    PRONOME_PATTERNS = {
        'docente': [
            r'\b(?:dele|dela)\b',
            r'\b(?:desse|dessa)\s+(?:professor|professora|docente)\b',
            r'\b(?:sobre|com)\s+(?:ele|ela)\b',
            r'\b(?:email|sala|contato|[aá]reas?)\s+(?:dele|dela)\b',
        ],
        'disciplina': [
            r'\b(?:essa|essa|desta|destra)\s+(?:disciplina|mat[eé]ria|cadeira)\b',
            r'\bpr[eé]-?requisitos?\s+(?:dela|dessa)\b',
            r'\bquem\s+leciona\s+(?:ela|essa)\b',
        ],
        'curso': [
            r'\b(?:desse|dessa|deste|desta)\s+(?:curso|gradua[cç][aã]o)\b',
            r'\bcoordenador(?:a)?\s+(?:desse|dessa|dele|dela)\b',
            r'\b(?:e\s+)?(?:no|do)\s+termo\s+\d+\b',  # "E no termo 6?" implica curso anterior
        ],
    }
    
    # Padrões de perguntas de follow-up curtas
    FOLLOWUP_PATTERNS = [
        r'^e\s+(?:as?|os?|no|na|do|da)\s+',  # "E as do termo 5?"
        r'^(?:e\s+)?qual\s+(?:deles|delas)\b',  # "Qual deles trabalha com..."
        r'^(?:e\s+)?quais?\s+(?:s[aã]o)?\s*\?',  # "E quais são?"
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
        
        # 1. Resolver referências a docentes (dele, dela, etc.)
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
    
    def _replace_docente_reference(self, question: str, docente: str) -> str:
        """Substitui referências pronominais por nome do docente."""
        replacements = [
            (r'\b(?:dele|dela)\b', f'do professor {docente}'),
            (r'\b(?:desse|dessa)\s+(?:professor|professora|docente)\b', f'do professor {docente}'),
            (r'\bcom\s+(?:ele|ela)\b', f'com o professor {docente}'),
            (r'\bsobre\s+(?:ele|ela)\b', f'sobre o professor {docente}'),
        ]
        result = question
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
    
    def _replace_disciplina_reference(self, question: str, disciplina: str) -> str:
        """Substitui referências a disciplina pelo nome."""
        replacements = [
            (r'\b(?:essa|esta|desta|dessa)\s+(?:disciplina|mat[eé]ria|cadeira)\b', disciplina),
            (r'\b(?:dela|dessa)\b(?=.*(?:pr[eé]-?requisito|quem\s+leciona))', f'de {disciplina}'),
        ]
        result = question
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
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
        context: ConversationContext
    ) -> str:
        """Expande pergunta de follow-up curta."""
        question_lower = question.lower()
        
        # "E no termo 6?" com curso no contexto
        termo_match = re.search(r'termo\s+(\d+)', question_lower)
        if termo_match and context.curso:
            novo_termo = termo_match.group(1)
            return f"Quais disciplinas do termo {novo_termo} de {context.curso}?"
        
        # Encontrar última pergunta do usuário e adaptar
        for msg in reversed(history):
            if msg['role'] == 'user':
                last_question = msg['content']
                
                # Se a pergunta atual menciona um novo termo, substituir na anterior
                if termo_match:
                    novo_termo = termo_match.group(1)
                    if re.search(r'termo\s+\d+', last_question, re.IGNORECASE):
                        return re.sub(
                            r'termo\s+\d+', 
                            f'termo {novo_termo}', 
                            last_question, 
                            flags=re.IGNORECASE
                        )
                break
        
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
                # "Para cursar X, são necessários..." 
                resp_patterns = [
                    r'(?:para\s+cursar|pr[eé]-requisitos?\s+(?:de|da|para))\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                    r'[Dd]ocentes?\s+(?:que\s+lecionam?|de)\s+([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                ]
                for pattern in resp_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        disc = match.group(1).strip()
                        if disc.lower() not in ['o', 'a', 'os', 'as', 'que', 'qual', 'quais', 'total']:
                            return disc
            
            # Depois verificar perguntas do usuário
            elif msg['role'] == 'user':
                patterns = [
                    r'pr[eé]-?requisitos?\s+(?:de|da|do|para)\s+([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                    r'quem\s+leciona\s+([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                    r'disciplina\s+(?:de\s+)?([A-Za-zÀ-ú]+(?:\s+[A-Za-zÀ-ú]+)*)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        disc = match.group(1).strip()
                        # Limpar pontuação
                        disc = re.sub(r'[\?.,!]+$', '', disc).strip()
                        # Filtrar palavras comuns
                        if disc.lower() not in ['o', 'a', 'os', 'as', 'que', 'qual', 'quais', 'essa', 'esse', 'ela']:
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
            # Invocar LLM
            response = llm.invoke(prompt)
            rewritten = response.strip()
            
            # Validar resposta
            if rewritten and len(rewritten) > 5 and len(rewritten) < 500:
                logger.info(f"[LLM REWRITE] '{question}' → '{rewritten}'")
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
        
        # Perguntas muito curtas são potencialmente ambíguas
        if len(question.split()) < 4:
            return True
        
        # Perguntas com pronomes não resolvidos
        ambiguous_patterns = [
            r'\b(?:ele|ela|eles|elas)\b',
            r'\b(?:isso|isto|aquilo)\b',
            r'\b(?:esse|essa|esses|essas)\s+(?!de\s)',  # "essa" mas não "essa de"
            r'\b(?:qual|quais)\s+(?:deles|delas)\b',
        ]
        
        for pattern in ambiguous_patterns:
            if re.search(pattern, question_lower):
                return True
        
        return False


# Instância global para uso na API
context_resolver = ContextResolver()

