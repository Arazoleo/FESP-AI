"""
Extrator de relações via LLM para enriquecer o Knowledge Graph.
Permite extrair relações de textos não estruturados automaticamente.
"""
import re
import json
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


@dataclass
class ExtractedRelation:
    """Representa uma relação extraída."""
    subject: str
    subject_type: str
    relation: str
    object: str
    object_type: str
    confidence: float
    source_text: str


class RelationExtractor:
    """
    Extrai relações de textos usando LLM.
    
    Tipos de entidades suportados:
    - DOCENTE: Professores
    - DISCIPLINA: Matérias/cursos
    - AREA: Áreas de conhecimento
    - CURSO: Cursos (BCC, BCT, etc)
    - ORGAO: Órgãos institucionais
    - CONCEITO: Conceitos acadêmicos
    
    Tipos de relações suportados:
    - LECIONA: Docente -> Disciplina
    - ESPECIALISTA_EM: Docente -> Área
    - PREREQUISITO_DE: Disciplina -> Disciplina
    - PERTENCE_A: Disciplina -> Curso
    - RELACIONADO_COM: Conceito -> Conceito
    - COORDENA: Docente -> Curso
    - PESQUISA: Docente -> Área
    - UTILIZA: Disciplina -> Conceito
    """
    
    # Relações válidas por tipo de entidade
    VALID_RELATIONS = {
        ('DOCENTE', 'DISCIPLINA'): ['LECIONA', 'COORDENA_DISCIPLINA'],
        ('DOCENTE', 'AREA'): ['ESPECIALISTA_EM', 'PESQUISA'],
        ('DOCENTE', 'CURSO'): ['COORDENA', 'VICE_COORDENA'],
        ('DISCIPLINA', 'DISCIPLINA'): ['PREREQUISITO_DE', 'RELACIONADA_COM', 'COMPLEMENTA'],
        ('DISCIPLINA', 'CURSO'): ['PERTENCE_A', 'ELETIVA_DE'],
        ('DISCIPLINA', 'CONCEITO'): ['ABORDA', 'UTILIZA', 'ENSINA'],
        ('CONCEITO', 'CONCEITO'): ['RELACIONADO_COM', 'DEPENDE_DE', 'PARTE_DE'],
        ('CONCEITO', 'AREA'): ['PERTENCE_A'],
        ('AREA', 'AREA'): ['SUBAREA_DE', 'RELACIONADA_COM'],
    }
    
    # Prompt otimizado para extração de relações acadêmicas
    EXTRACTION_PROMPT = """Você é um especialista em extração de informações de textos acadêmicos.

Analise o texto abaixo e extraia TODAS as relações entre entidades.

TIPOS DE ENTIDADES:
- DOCENTE: Nomes de professores (Prof., Dr., Dra.)
- DISCIPLINA: Nomes de matérias/disciplinas
- AREA: Áreas de conhecimento (Machine Learning, Banco de Dados, etc)
- CURSO: Nomes de cursos (BCC, Ciência da Computação, etc)
- CONCEITO: Conceitos técnicos/acadêmicos

TIPOS DE RELAÇÕES:
- LECIONA: Docente ensina uma Disciplina
- ESPECIALISTA_EM: Docente é especialista em uma Área
- PESQUISA: Docente pesquisa uma Área
- PREREQUISITO_DE: Uma Disciplina é pré-requisito de outra
- RELACIONADA_COM: Entidades relacionadas
- PERTENCE_A: Disciplina pertence a um Curso
- COORDENA: Docente coordena um Curso
- ABORDA: Disciplina aborda um Conceito
- UTILIZA: Disciplina utiliza um Conceito

TEXTO:
{text}

Responda APENAS com um JSON válido no formato:
{{
  "relations": [
    {{
      "subject": "nome da entidade 1",
      "subject_type": "TIPO",
      "relation": "RELACAO",
      "object": "nome da entidade 2", 
      "object_type": "TIPO",
      "confidence": 0.9
    }}
  ]
}}

Se não encontrar relações, retorne: {{"relations": []}}

IMPORTANTE:
- Extraia APENAS relações claramente indicadas no texto
- Use confidence entre 0.5 e 1.0
- Normalize nomes (remover Prof., Dr., etc do início)
- Seja conservador: prefira não extrair a extrair errado
"""

    def __init__(self, llm: OllamaLLM = None, ollama_base_url: str = None, model_name: str = "qwen2.5:7b"):
        """
        Inicializa o extrator.
        
        Args:
            llm: Instância do LLM (opcional, cria uma se não fornecida)
            ollama_base_url: URL do Ollama
            model_name: Nome do modelo (recomendado: qwen2.5:7b para melhor extração)
        """
        if llm:
            self.llm = llm
        else:
            if ollama_base_url:
                self.llm = OllamaLLM(
                    model=model_name,
                    base_url=ollama_base_url,
                    temperature=0.1,  # Baixa temperatura para consistência
                    num_predict=2048,
                    timeout=120  # Timeout maior para textos longos
                )
            else:
                self.llm = OllamaLLM(
                    model=model_name,
                    temperature=0.1,
                    num_predict=2048,
                    timeout=120
                )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Você é um assistente especializado em extração de informações estruturadas de textos acadêmicos."),
            ("human", self.EXTRACTION_PROMPT)
        ])
        self.chain = self.prompt | self.llm
    
    def _parse_llm_response(self, response: str) -> List[Dict]:
        """Parse a resposta do LLM para extrair o JSON."""
        try:
            # Tentar encontrar JSON na resposta
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('relations', [])
        except json.JSONDecodeError as e:
            logger.warning(f"Erro ao parsear JSON do LLM: {e}")
        return []
    
    def _validate_relation(self, rel: Dict) -> bool:
        """Valida se a relação extraída é válida."""
        required_fields = ['subject', 'subject_type', 'relation', 'object', 'object_type']
        
        # Verificar campos obrigatórios
        for field in required_fields:
            if field not in rel or not rel[field]:
                return False
        
        # Verificar tipos de entidade válidos
        valid_types = {'DOCENTE', 'DISCIPLINA', 'AREA', 'CURSO', 'CONCEITO', 'ORGAO'}
        if rel['subject_type'] not in valid_types or rel['object_type'] not in valid_types:
            return False
        
        # Verificar se a relação é válida para os tipos de entidade
        type_pair = (rel['subject_type'], rel['object_type'])
        valid_relations = self.VALID_RELATIONS.get(type_pair, [])
        
        # Permitir relações genéricas
        if rel['relation'] not in valid_relations and rel['relation'] != 'RELACIONADO_COM':
            logger.debug(f"Relação '{rel['relation']}' não válida para {type_pair}")
            # Não invalidar, mas ajustar para relação genérica
            rel['relation'] = 'RELACIONADO_COM'
        
        return True
    
    def _normalize_entity(self, name: str, entity_type: str) -> str:
        """Normaliza o nome de uma entidade."""
        name = name.strip()
        
        if entity_type == 'DOCENTE':
            # Remover títulos comuns
            name = re.sub(r'^(Prof\.?a?|Dr\.?a?|Doutor\.?a?|Mestre?)\s*', '', name, flags=re.IGNORECASE)
            name = name.strip()
        
        return name
    
    def extract_from_text(self, text: str, min_confidence: float = 0.6) -> List[ExtractedRelation]:
        """
        Extrai relações de um texto.
        
        Args:
            text: Texto para extração
            min_confidence: Confiança mínima para aceitar relação
            
        Returns:
            Lista de relações extraídas
        """
        if not text or len(text.strip()) < 50:
            return []
        
        try:
            # Limitar texto para evitar timeout
            text_truncated = text[:4000] if len(text) > 4000 else text
            
            response = self.chain.invoke({"text": text_truncated})
            raw_relations = self._parse_llm_response(response)
            
            relations = []
            for rel in raw_relations:
                if not self._validate_relation(rel):
                    continue
                
                confidence = float(rel.get('confidence', 0.5))
                if confidence < min_confidence:
                    continue
                
                extracted = ExtractedRelation(
                    subject=self._normalize_entity(rel['subject'], rel['subject_type']),
                    subject_type=rel['subject_type'],
                    relation=rel['relation'],
                    object=self._normalize_entity(rel['object'], rel['object_type']),
                    object_type=rel['object_type'],
                    confidence=confidence,
                    source_text=text_truncated[:200] + "..."
                )
                relations.append(extracted)
            
            logger.info(f"Extraídas {len(relations)} relações do texto")
            return relations
            
        except Exception as e:
            logger.error(f"Erro na extração de relações: {e}")
            return []
    
    def extract_from_documents(self, documents: List[Dict], min_confidence: float = 0.6) -> List[ExtractedRelation]:
        """
        Extrai relações de múltiplos documentos.
        
        Args:
            documents: Lista de dicts com 'content' e opcionalmente 'metadata'
            min_confidence: Confiança mínima
            
        Returns:
            Lista de todas as relações extraídas
        """
        all_relations = []
        
        for i, doc in enumerate(documents):
            content = doc.get('content', doc.get('page_content', ''))
            logger.info(f"Processando documento {i+1}/{len(documents)}...")
            
            relations = self.extract_from_text(content, min_confidence)
            all_relations.extend(relations)
        
        # Remover duplicatas
        unique_relations = self._deduplicate_relations(all_relations)
        
        logger.info(f"Total: {len(unique_relations)} relações únicas extraídas de {len(documents)} documentos")
        return unique_relations
    
    def _deduplicate_relations(self, relations: List[ExtractedRelation]) -> List[ExtractedRelation]:
        """Remove relações duplicadas, mantendo a de maior confiança."""
        seen = {}
        
        for rel in relations:
            key = (rel.subject.lower(), rel.relation, rel.object.lower())
            if key not in seen or rel.confidence > seen[key].confidence:
                seen[key] = rel
        
        return list(seen.values())
    
    def relations_to_graph_format(self, relations: List[ExtractedRelation]) -> List[Dict]:
        """
        Converte relações para formato compatível com KnowledgeGraph.
        
        Returns:
            Lista de dicts com 'source', 'target', 'relation', 'metadata'
        """
        graph_relations = []
        
        for rel in relations:
            # Mapear tipo para prefixo do KnowledgeGraph
            type_prefix = {
                'DOCENTE': 'DOC',
                'DISCIPLINA': 'DISC',
                'AREA': 'AREA',
                'CURSO': 'CURSO',
                'CONCEITO': 'CONCEITO',
                'ORGAO': 'ORGAO'
            }
            
            source_prefix = type_prefix.get(rel.subject_type, 'ENT')
            target_prefix = type_prefix.get(rel.object_type, 'ENT')
            
            graph_relations.append({
                'source_id': f"{source_prefix}:{rel.subject}",
                'source_type': rel.subject_type.lower(),
                'source_name': rel.subject,
                'target_id': f"{target_prefix}:{rel.object}",
                'target_type': rel.object_type.lower(),
                'target_name': rel.object,
                'relation': rel.relation,
                'confidence': rel.confidence,
                'extracted': True  # Flag para identificar relações extraídas vs manuais
            })
        
        return graph_relations


class KnowledgeGraphEnricher:
    """
    Enriquece o KnowledgeGraph com relações extraídas via LLM.
    """
    
    def __init__(self, knowledge_graph, relation_extractor: RelationExtractor):
        """
        Args:
            knowledge_graph: Instância do KnowledgeGraph
            relation_extractor: Instância do RelationExtractor
        """
        self.kg = knowledge_graph
        self.extractor = relation_extractor
        self.added_relations = []
    
    def enrich_from_text(self, text: str, min_confidence: float = 0.7) -> int:
        """
        Extrai relações de texto e adiciona ao grafo.
        
        Args:
            text: Texto para processar
            min_confidence: Confiança mínima (maior para enriquecimento)
            
        Returns:
            Número de relações adicionadas
        """
        relations = self.extractor.extract_from_text(text, min_confidence)
        graph_rels = self.extractor.relations_to_graph_format(relations)
        
        added = 0
        for rel in graph_rels:
            try:
                # Criar nós se não existirem
                if not self.kg.graph.has_node(rel['source_id']):
                    self.kg.graph.add_node(
                        rel['source_id'],
                        tipo=rel['source_type'],
                        nome=rel['source_name'],
                        extracted=True
                    )
                
                if not self.kg.graph.has_node(rel['target_id']):
                    self.kg.graph.add_node(
                        rel['target_id'],
                        tipo=rel['target_type'],
                        nome=rel['target_name'],
                        extracted=True
                    )
                
                # Adicionar aresta
                self.kg.graph.add_edge(
                    rel['source_id'],
                    rel['target_id'],
                    relacao=rel['relation'],
                    confidence=rel['confidence'],
                    extracted=True
                )
                
                self.added_relations.append(rel)
                added += 1
                
            except Exception as e:
                logger.error(f"Erro ao adicionar relação ao grafo: {e}")
        
        logger.info(f"Adicionadas {added} relações ao grafo")
        return added
    
    def enrich_from_documents(self, documents: List[Dict], min_confidence: float = 0.7) -> int:
        """
        Enriquece o grafo a partir de múltiplos documentos.
        
        Returns:
            Total de relações adicionadas
        """
        total_added = 0
        
        for i, doc in enumerate(documents):
            content = doc.get('content', doc.get('page_content', ''))
            logger.info(f"Enriquecendo a partir do documento {i+1}/{len(documents)}...")
            
            added = self.enrich_from_text(content, min_confidence)
            total_added += added
        
        return total_added
    
    def get_extraction_stats(self) -> Dict:
        """Retorna estatísticas das extrações realizadas."""
        if not self.added_relations:
            return {'total': 0, 'by_relation': {}, 'by_type': {}}
        
        by_relation = {}
        by_type = {}
        
        for rel in self.added_relations:
            # Contar por tipo de relação
            r = rel['relation']
            by_relation[r] = by_relation.get(r, 0) + 1
            
            # Contar por tipo de entidade
            for t in [rel['source_type'], rel['target_type']]:
                by_type[t] = by_type.get(t, 0) + 1
        
        return {
            'total': len(self.added_relations),
            'by_relation': by_relation,
            'by_type': by_type,
            'avg_confidence': sum(r['confidence'] for r in self.added_relations) / len(self.added_relations)
        }

