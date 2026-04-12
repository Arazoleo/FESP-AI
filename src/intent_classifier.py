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
        # ementa_disciplina tem PRIORIDADE sobre prerequisite_chain — "o que é X?" ≠ pré-req
        'ementa_disciplina': r'o\s+que\s+[eé]\s+|o\s+que\s+(?:se\s+)?(?:estuda|aprende)\s+em\b|descreva\s+a?\s+disciplina',
        'prerequisite_chain': r'pr[eé][-\s]?requisitos?',
        'dependents': r'depend(?:e|em)\s+de',
        'discipline_docentes': r'quem\s+(?:leciona|d[aá]|ensina)',
        'docente_info': r'(?:email|e-mail|sala|contato)\s+(?:de|do|da)',
        'listar_cursos': r'cursos?\s+(?:da\s+)?(?:unifesp|ict)',
        'eletivas_curso': r'eletivas?',
        'coordenador_curso': r'coordena(?:dor|ção)',
    }
    
    # Padrões para extração de termos por intenção
    TERM_PATTERNS = {
        'ementa_disciplina': [
            r'o\s+que\s+[eé]\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
            r'o\s+que\s+(?:se\s+)?(?:estuda|aprende)\s+em\s+(.+?)(?:\?|$)',
            r'descreva\s+a?\s+disciplina\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'do\s+que\s+trata\s+(.+?)(?:\?|$)',
        ],
        'prerequisite_chain': [
            r'pr[eé][-\s]?requisitos?\s+(?:de|da|do|para)\s+(.+?)(?:\?|$)',
            r'antes\s+de\s+(?:fazer\s+|cursar\s+)?(.+?)(?:\?|$)',
            r'para\s+(?:fazer|cursar)\s+(.+?)(?:\?|$)',
            # "E de Compiladores, quais são os pré-requisitos?"
            r'^e\s+(?:de|sobre)\s+([A-Za-zÀ-ú\s]+?)(?:,|\?|$)',
            # "E de X? / E sobre X?"
            r'^e\s+(?:de|sobre)\s+(.+?)(?:,|\s+quais?|\s+os?|\?)',
        ],
        'dependents': [
            r'depend(?:e|em)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            r'(?:usam?|precisam?|exigem?)\s+(.+?)\s+como',
        ],
        'discipline_docentes': [
            # "Quem leciona Compiladores?" / "Quais docentes dão Cálculo Numérico?"
            r'(?:leciona|ensina|ministra)\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
            r'd[aá]\s+aula\s+(?:de\s+)?(.+?)(?:\?|$)',
            r'(?:professore?s?|docentes?)\s+(?:d[aã]o|de|da|do)\s+(.+?)(?:\?|$)',
            r'd[aã]o\s+([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)(?:\?|$)',
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
    }
    
    def __init__(self, embeddings_model=None):
        """
        Inicializa o classificador.
        
        Args:
            embeddings_model: Modelo de embeddings (OllamaEmbeddings ou similar)
        """
        self.embeddings_model = embeddings_model
        self._intent_embeddings: Dict[str, np.ndarray] = {}
        self._initialized = False
    
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
        }
        
        words = question_lower.split()
        terms = [w for w in words if w not in stopwords and len(w) > 2]
        
        if terms:
            return ' '.join(terms[-3:])  # Últimas 3 palavras relevantes
        
        return ""
    
    def classify(self, question: str) -> ClassificationResult:
        """
        Classifica a intenção de uma pergunta.
        
        Returns:
            ClassificationResult com intent, term, confidence e method
        """
        question_lower = question.lower().strip()
        
        # 1. Verificar padrões regex óbvios (boost de confiança)
        quick_intent = self._quick_regex_check(question)
        
        # 2. Se temos embeddings, usar classificação semântica
        if self._initialized and self.embeddings_model:
            try:
                # Gerar embedding da pergunta
                question_embedding = np.array(
                    self.embeddings_model.embed_query(question)
                )
                
                # Calcular similaridade com cada intenção
                best_intent = None
                best_score = -1.0
                
                for intent, centroid in self._intent_embeddings.items():
                    similarity = self._cosine_similarity(question_embedding, centroid)
                    
                    # Boost se regex também detectou
                    if intent == quick_intent:
                        similarity = min(1.0, similarity + 0.15)
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_intent = intent
                
                # Threshold de confiança
                if best_score >= 0.45:
                    term = self._extract_term(question, best_intent)
                    return ClassificationResult(
                        intent=best_intent,
                        term=term,
                        confidence=best_score,
                        method='embeddings'
                    )
            
            except Exception as e:
                print(f"[IntentClassifier] Erro nos embeddings: {e}")
        
        # 3. Fallback para regex se quick_intent foi detectado
        if quick_intent:
            term = self._extract_term(question, quick_intent)
            return ClassificationResult(
                intent=quick_intent,
                term=term,
                confidence=0.7,
                method='regex'
            )
        
        # 4. Não conseguiu classificar
        return ClassificationResult(
            intent='unknown',
            term='',
            confidence=0.0,
            method='none'
        )
    
    def classify_batch(self, questions: List[str]) -> List[ClassificationResult]:
        """Classifica múltiplas perguntas de uma vez."""
        return [self.classify(q) for q in questions]

