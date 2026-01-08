import re
from typing import Optional, List, Dict, Tuple
from .knowledge_graph import KnowledgeGraph

class GraphRAGEngine:
    """Metodologia híbrida GraphRAG + RAG"""

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        
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
                r'quem\s+(?:leciona|ensina|ministra|d[aá])\s+(.+?)(?:\?|$)',
                r'(?:quais?\s+)?(?:os?\s+)?(?:professore?s?|docentes?)\s+(?:de|da|do)\s+(.+?)(?:\?|$)',
            ],
            'artigos_sobre': [
                r'(?:quais?\s+)?artigos?\s+(?:sobre|que\s+(?:falam?|tratam?|mencionam?))\s+(.+?)(?:\?|$)',
                r'(?:o\s+que|quais?)\s+(?:os?\s+)?(?:artigos?|regras?|normas?)\s+(?:dizem?|falam?)\s+sobre\s+(.+?)(?:\?|$)',
            ],
            'faqs': [
                r'(?:perguntas?\s+)?(?:frequentes?|comuns?)\s+sobre\s+(.+?)(?:\?|$)',
                r'(?:d[uú]vidas?\s+)?(?:sobre|comuns?\s+sobre)\s+(.+?)(?:\?|$)',
            ],
        }
    
    def should_use_graph(self, question: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Determina se a pergunta deve usar GraphRAG.
        Retorna: (usar_graph, tipo_query, termo_extraido)
        """
        question_lower = question.lower().strip()
        
        for query_type, patterns in self.graph_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, question_lower, re.IGNORECASE)
                if match:
                    termo = match.group(1).strip()
                    termo = re.sub(r'[\?.,!]+$', '', termo).strip()
                    termo = re.sub(r'\s+(da|de|do|na|no|em)$', '', termo, flags=re.IGNORECASE).strip()
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