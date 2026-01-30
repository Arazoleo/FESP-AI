import re
from typing import Optional, List, Dict, Tuple
from .knowledge_graph import KnowledgeGraph
from .intent_classifier import IntentClassifier, ClassificationResult

class GraphRAGEngine:
    """Metodologia híbrida GraphRAG + RAG"""

    def __init__(self, knowledge_graph: KnowledgeGraph, embeddings_model=None):
        self.kg = knowledge_graph
        
        # Novo classificador de intenção baseado em embeddings
        self.intent_classifier = IntentClassifier(embeddings_model)
        self._use_semantic_classification = embeddings_model is not None
        
        # Patterns regex legados (fallback)
        self.graph_patterns = {
            'prerequisite_chain': [
                r'(?:quais?|todos?)\s+(?:os?\s+)?pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
                r'(?:o\s+que|quais?\s+disciplinas?)\s+(?:preciso|precisa|devo|deve)\s+(?:fazer|cursar|ter)\s+(?:antes\s+de|para\s+fazer|para\s+cursar)\s+(.+?)(?:\?|$)',
                r'cadeia\s+(?:de\s+)?pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
            ],
            'dependents': [
                r'(?:quais?\s+)?disciplinas?\s+(?:que\s+)?depend(?:e|em)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?disciplinas?\s+(?:que\s+)?(?:usam?|precisam?|requerem?|exigem?)\s+(.+?)\s+como\s+pr[eé][-\s]?requisito(?:\?|$)',
                r'(?:para\s+)?(?:o\s+)?que\s+(.+?)\s+[eé]\s+pr[eé][-\s]?requisito(?:\?|$)',
            ],
            'docente_disciplines': [
                r'(?:quais?\s+)?(?:disciplinas?|mat[eé]rias?)\s+(?:que\s+)?(?:o\s+|a\s+)?(?:professor(?:a)?|docente)?\s*(.+?)\s+(?:leciona|ensina|ministra|d[aá])(?:\?|$)',
                r'(?:o\s+que|quais?)\s+(?:o\s+|a\s+)?(.+?)\s+(?:leciona|ensina|ministra|d[aá])(?:\?|$)',
            ],
            'discipline_docentes': [
                # IMPORTANTE: Deve vir ANTES de docente_leciona_disciplina para "quem leciona X?"
                r'quem\s+(?:leciona|ensina|ministra|d[aá])\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:de|da|do|que\s+d[aã]o)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:que\s+)?(?:lecionam?|ensinam?|ministram?|d[aã]o)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            ],
            'docente_leciona_disciplina': [
                # Padrão: "O professor X leciona Y?" - retorna (docente, disciplina)
                # Exige "professor" ou "docente" para evitar confusão com "quem leciona X?"
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
                # Padrões para perguntas com referência a IC/pesquisa
                r'(?:quero\s+fazer\s+(?:uma?\s+)?(?:ic|inicia[çc][aã]o\s+cient[ií]fica)\s+com\s+(?:o\s+|a\s+)?(.+?))[\.,]\s*(?:qual|pode\s+me\s+dizer)\s+(?:a\s+)?[aá]rea',
                r'(?:pode\s+me\s+dizer|me\s+diz(?:er)?|qual\s+[eé])\s+(?:a\s+)?[aá]rea\s+(?:de|do|da)\s+(?:o\s+|a\s+)?(.+?)(?:\?|$)',
                # Padrões com pronomes (já resolvidos para nome pela API)
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
                # Padrões MAIS ESPECÍFICOS primeiro (com "grupo")
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:as?\s+)?eletivas?\s+do\s+grupo\s+\d+\s+(?:de|do|da|para)\s+(.+?)(?:\?|$)',
                # Padrões GERAIS depois
                r'(?:como\s+)?funcionam?\s+(?:as?\s+)?(?:disciplinas?\s+)?eletivas?\s+(?:de|do|da|no|na)\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:s[aã]o\s+)?(?:as?\s+)?eletivas?\s+(?:de|do|da|para|d[oe])\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?disciplinas?\s+eletivas?\s+(?:de|do|da|para)\s+(.+?)(?:\?|$)',
                r'eletivas?\s+(?:dispon[ií]veis?\s+)?(?:para|no|na|do|da|de)\s+(.+?)(?:\?|$)',
                r'(?:liste|mostre|quero\s+ver)\s+(?:as?\s+)?eletivas?\s+(?:de|do|da)\s+(.+?)(?:\?|$)',
            ],
            'matriz_info': [
                r'(?:qual|como\s+[eé])\s+(?:a\s+)?matriz\s+(?:curricular\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:qual|como\s+[eé])\s+(?:a\s+)?estrutura\s+(?:do\s+curso\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'estrutura\s+(?:curricular\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'quantos?\s+termos?\s+(?:tem|possui|dura)\s+(?:o\s+)?(?:curso\s+)?(?:de\s+)?(.+?)(?:\?|$)',
                r'dura[çc][aã]o\s+(?:do\s+curso\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:carga\s+hor[aá]ria\s+)?(?:total\s+)?(?:de|do|da)\s+(.+?)(?:\?|$)',
                r'(?:quantas?\s+)?horas?\s+(?:tem|precisa|possui)\s+(?:o\s+)?(?:curso\s+)?(?:de\s+)?(.+?)(?:\?|$)',
                # Padrões conversacionais
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
        # 1. Tentar classificação semântica primeiro
        if self._use_semantic_classification and self.intent_classifier._initialized:
            result = self.intent_classifier.classify(question)
            
            if result.intent != 'unknown' and result.confidence >= 0.45:
                # Pós-processamento para casos especiais
                termo = self._post_process_term(question, result.intent, result.term)
                return True, result.intent, termo
        
        # 2. Fallback para regex (mantém compatibilidade)
        return self._regex_fallback(question)
    
    def _post_process_term(self, question: str, intent: str, term: str) -> str:
        """Pós-processamento do termo extraído para casos especiais."""
        question_lower = question.lower()
        
        # Caso especial: listar_cursos não precisa de termo
        if intent == 'listar_cursos':
            return ""
        
        # Caso especial: docente_leciona_disciplina precisa de "docente:disciplina"
        if intent == 'docente_leciona_disciplina':
            # Tentar extrair docente e disciplina
            match = re.search(
                r'(?:professor(?:a)?|docente)\s+(.+?)\s+(?:leciona|d[aá]|ensina)\s+(.+?)(?:\?|$)',
                question_lower
            )
            if match:
                docente = match.group(1).strip()
                disciplina = match.group(2).strip()
                disciplina = re.sub(r'[\?.,!]+$', '', disciplina).strip()
                return f"{docente}:{disciplina}"
        
        # Caso especial: disciplinas_termo precisa de "numero:curso"
        if intent == 'disciplinas_termo':
            # Verificar se já está no formato correto
            if ':' in term:
                return term
            # Tentar extrair número do termo
            match = re.search(r'(?:termo|semestre)\s+(\d+)', question_lower)
            if match:
                numero = match.group(1)
                # Remover o número do termo extraído
                curso = re.sub(r'\d+\s*', '', term).strip()
                if curso:
                    return f"{numero}:{curso}"
        
        return term
    
    def _regex_fallback(self, question: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Fallback para classificação baseada em regex (método legado)."""
        question_lower = question.lower().strip()
        
        for query_type, patterns in self.graph_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, question_lower, re.IGNORECASE)
                if match:
                    # Caso especial para listar_cursos (sem grupo de captura)
                    if query_type == 'listar_cursos':
                        return True, query_type, ""
                    # Caso especial para disciplinas_termo (dois grupos)
                    elif query_type == 'disciplinas_termo' and len(match.groups()) >= 2:
                        termo_num = match.group(1).strip()
                        # Converter números por extenso para dígitos
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
                    # Caso especial para docente_leciona_disciplina (dois grupos)
                    elif query_type == 'docente_leciona_disciplina' and len(match.groups()) >= 2:
                        docente = match.group(1).strip()
                        disciplina = match.group(2).strip()
                        # Limpar pontuação
                        docente = re.sub(r'[\?.,!]+$', '', docente).strip()
                        disciplina = re.sub(r'[\?.,!]+$', '', disciplina).strip()
                        termo = f"{docente}:{disciplina}"
                    elif match.groups():
                        termo = match.group(1).strip()
                        termo = re.sub(r'[\?.,!]+$', '', termo).strip()
                        termo = re.sub(r'\s+(da|de|do|na|no|em)$', '', termo, flags=re.IGNORECASE).strip()
                    else:
                        termo = ""
                    return True, query_type, termo
        
        return False, None, None
    
    def query_graph(self, query_type: str, termo: str) -> Optional[str]:
        """
        Executa uma query no Knowledge Graph e formata a resposta.
        """
        if query_type == 'prerequisite_chain':
            chain = self.kg.get_prerequisite_chain(termo)
            if chain:
                # Formatar como caminho
                path = f"{termo} ← " + " ← ".join(chain)
                return f"""**Cadeia de pré-requisitos de {termo}:**
{path}

Para cursar **{termo}**, você precisa ter cursado anteriormente:
{chr(10).join(f'- {d}' for d in chain)}

Total: {len(chain)} pré-requisito(s) na cadeia."""
            else:
                return f"**{termo}** não possui pré-requisitos ou não foi encontrada no sistema."
        
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
            # termo vem como "docente:disciplina"
            if ':' in termo:
                docente, disciplina = termo.split(':', 1)
                disciplinas = self.kg.get_disciplines_of_docente(docente)
                docente_titulo = docente.title()
                
                # Mapeamento de siglas comuns para nomes de disciplinas
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
                    # Verificar se a disciplina específica está na lista
                    disc_lower = disciplina.lower()
                    # Expandir sigla se for uma sigla conhecida
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
                for art in artigos[:5]:  # Limitar a 5
                    resultado += f"- **Art. {art['numero']}** ({art['documento']}): {art['conteudo']}\n\n"
                return resultado
            else:
                return f"Não encontrei artigos sobre **{termo}**."
        
        elif query_type == 'faqs':
            faqs = self.kg.get_faqs_sobre(termo)
            if faqs:
                resultado = f"**Perguntas frequentes sobre '{termo}':**\n\n"
                for faq in faqs[:5]:  # Limitar a 5
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
                return f"Não encontrei informações sobre as áreas de **{termo}**."
        
        elif query_type == 'docente_info':
            info = self.kg.get_docente_info(termo)
            if info:
                resultado = f"**Informações de {info['nome']}:**\n\n"
                if info.get('email'):
                    resultado += f"- **Email:** {info['email']}\n"
                if info.get('sala'):
                    resultado += f"- **Sala:** {info['sala']}\n"
                if info.get('areas'):
                    resultado += f"- **Áreas:** {info['areas']}\n"
                return resultado
            else:
                return f"Não encontrei informações sobre **{termo}**."
        
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
                # Usar 'curso' em vez de 'nome' (retorno de get_coordenador)
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
            # termo vem como "numero:curso"
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
                # Obter informações da matriz
                info = self.kg.get_info_matriz(termo)
                curso_nome = info.get('nome', termo.upper()) if info else termo.upper()
                duracao = info.get('duracao_termos', str(len(termos))) if info else str(len(termos))
                
                resultado = f"**Disciplinas da Matriz Curricular de {curso_nome}**\n"
                resultado += f"*Total de {duracao} termos (semestres)*\n\n"
                
                # Ordenar termos
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
            # Extrair grupo se especificado (ex: "Grupo 1 do BCC")
            grupo_filtro = None
            curso_limpo = termo
            
            grupo_match = re.search(r'(?:grupo\s+|g)(\d+)', termo, re.IGNORECASE)
            if grupo_match:
                num_grupo = grupo_match.group(1)
                grupo_filtro = f"grupo{num_grupo}"
                # Remover a parte do grupo para extrair o curso
                curso_limpo = re.sub(r'\s*(?:grupo\s+|g)\d+\s*(?:de|do|da)?\s*', '', termo, flags=re.IGNORECASE).strip()
            
            eletivas = self.kg.get_eletivas_do_curso(curso_limpo, grupo=grupo_filtro)
            if eletivas:
                # Agrupar por tipo
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
                
                # Ordenar grupos para apresentação consistente
                ordem_grupos = ['eletiva_grupo1', 'eletiva_grupo2', 'eletiva_grupo3', 'eletiva_extensionista']
                grupos_ordenados = sorted(grupos.keys(), key=lambda x: ordem_grupos.index(x) if x in ordem_grupos else 99)
                
                for grupo in grupos_ordenados:
                    disciplinas = grupos[grupo]
                    # Traduzir nome do grupo
                    nomes_grupos = {
                        'eletiva_grupo1': 'Grupo 1 - Eletivas Limitadas de Ciência da Computação',
                        'eletiva_grupo2': 'Grupo 2 - Eletivas de Matemática e Computação',
                        'eletiva_grupo3': 'Grupo 3 - Eletivas de Ciências Humanas, Econômicas e Sociais',
                        'eletiva_extensionista': 'Eletivas Extensionistas',
                    }
                    grupo_nome = nomes_grupos.get(grupo, grupo.replace('_', ' ').title())
                    resultado += f"**{grupo_nome}:**\n"
                    for d in disciplinas:  # Mostrar TODAS as disciplinas
                        resultado += f"- {d}\n"
                    resultado += "\n"
                
                resultado += f"\n**Total:** {len(eletivas)} eletivas disponíveis."
                return resultado
            else:
                return f"Não encontrei eletivas para **{curso_limpo}**."
        
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