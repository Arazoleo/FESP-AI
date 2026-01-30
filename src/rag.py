import os
import re
import json
import hashlib
import warnings
from pathlib import Path
from typing import Dict, List, Optional
from .knowledge_graph import KnowledgeGraph
from .graph_rag import GraphRAGEngine
from .relation_extractor import RelationExtractor, KnowledgeGraphEnricher

warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

from .config import Config
from .parsers_md import parse_file


class SemanticChunker:
    """Chunker inteligente que preserva documentos semanticos pequenos."""
    
    def __init__(self, max_chunk_size: int = 1500, chunk_overlap: int = 100):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        result = []
        for doc in documents:
            content_len = len(doc.page_content)
            if content_len <= self.max_chunk_size:
                result.append(doc)
            else:
                splits = self.fallback_splitter.split_documents([doc])
                disciplina = doc.metadata.get('disciplina', '')
                codigo = doc.metadata.get('codigo', '')
                secao = doc.metadata.get('secao', '')
                for i, split in enumerate(splits):
                    if disciplina and not split.page_content.startswith('DISCIPLINA:'):
                        context_header = f"[Continuacao - {disciplina} ({codigo}) - {secao}]\n\n"
                        split.page_content = context_header + split.page_content
                    split.metadata['chunk_index'] = i
                    split.metadata['total_chunks'] = len(splits)
                    result.append(split)
        return result


class RAGUnifesp:
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        ollama_base_url = self.config.OLLAMA_BASE_URL
        keep_alive_seconds = 3600
        # Timeout para evitar requests travadas (60 segundos) - apenas para LLM
        llm_timeout = 60
        
        if ollama_base_url and ollama_base_url != "http://localhost:11434":
            self.llm = OllamaLLM(
                model=self.config.MODEL_NAME, 
                base_url=ollama_base_url,
                keep_alive=keep_alive_seconds,
                num_predict=2048,
                temperature=0.1,
                top_k=10,
                repeat_penalty=1.1,
                timeout=llm_timeout
            )
            self.embeddings = OllamaEmbeddings(
                model=self.config.EMBEDDING_MODEL, 
                base_url=ollama_base_url,
                keep_alive=keep_alive_seconds
            )
        else:
            self.llm = OllamaLLM(
                model=self.config.MODEL_NAME, 
                keep_alive=keep_alive_seconds,
                num_predict=2048,
                temperature=0.1,
                top_k=10,
                repeat_penalty=1.1,
                timeout=llm_timeout
            )
            self.embeddings = OllamaEmbeddings(
                model=self.config.EMBEDDING_MODEL, 
                keep_alive=keep_alive_seconds
            )
        
        self.db = None
        self.retriever = None
        self.chain = None
        self.knowledge_graph = None
        self.graph_rag = None
        self.relation_extractor = None
        self.graph_enricher = None
    
    def _get_file_hash(self, filepath: str) -> str:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _load_index(self) -> Dict:
        index_path = self.config.get_index_path()
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                return json.load(f)
        return {"files": {}}
    
    def _save_index(self, index: Dict):
        os.makedirs(self.config.PERSIST_DIR, exist_ok=True)
        with open(self.config.get_index_path(), 'w') as f:
            json.dump(index, f, indent=2)
    
    def _detect_changes(self) -> tuple:
        index = self._load_index()
        changes = {"new": [], "modified": [], "deleted": []}
        current_files = {}
        
        for source_type, directory in self.config.SOURCES.items():
            if not os.path.exists(directory):
                continue
            for md_file in Path(directory).glob("*.md"):
                filepath = str(md_file)
                file_hash = self._get_file_hash(filepath)
                current_files[filepath] = file_hash
                
                if filepath not in index["files"]:
                    changes["new"].append(filepath)
                elif index["files"][filepath] != file_hash:
                    changes["modified"].append(filepath)
        
        for filepath in index["files"]:
            if filepath not in current_files:
                changes["deleted"].append(filepath)
        
        return changes, current_files
    
    def sync(self, force: bool = False) -> bool:
        changes, current_files = self._detect_changes()
        
        has_changes = any(changes.values())
        db_exists = os.path.exists(self.config.PERSIST_DIR) and os.path.exists(
            os.path.join(self.config.PERSIST_DIR, "chroma.sqlite3")
        )
        
        if not has_changes and db_exists and not force:
            print("Banco atualizado, nenhuma mudanca detectada.")
            self._load_db()
            self._setup_retriever()
            self._setup_chain()
            self._setup_knowledge_graph()
            return False
        
        if force or not db_exists:
            print("Recriando banco vetorial...")
            all_docs = []
            for filepath in current_files:
                all_docs.extend(parse_file(filepath))
            
            chunker = SemanticChunker(
                max_chunk_size=self.config.CHUNK_SIZE,
                chunk_overlap=self.config.CHUNK_OVERLAP
            )
            splits = chunker.split_documents(all_docs)
            
            self.db = Chroma.from_documents(
                splits,
                self.embeddings,
                persist_directory=self.config.PERSIST_DIR
            )
            self._save_index({"files": current_files})
            print(f"Banco criado: {len(splits)} chunks de {len(current_files)} arquivos.")
        else:
            self._load_db()
            self._apply_changes(changes, current_files)
        
        self._setup_retriever()
        self._setup_chain()
        self._setup_knowledge_graph()
        return True
    
    def _setup_knowledge_graph(self):
        """Inicializa o Knowledge Graph com classificador semântico."""
        try:
            self.knowledge_graph = KnowledgeGraph()
            
            # Verificar diretórios opcionais
            docentes_dir = getattr(self.config, 'DOCENTES_DIR', None)
            cursos_dir = getattr(self.config, 'CURSOS_DIR', None)
            
            # Passar diretórios que existem
            docentes_arg = str(docentes_dir) if docentes_dir and os.path.exists(docentes_dir) else None
            cursos_arg = str(cursos_dir) if cursos_dir and os.path.exists(cursos_dir) else None
            
            self.knowledge_graph.build_from_directories(
                str(self.config.DISCIPLINAS_DIR),
                str(self.config.REGIMENTOS_DIR),
                docentes_arg,
                cursos_arg
            )
            
            # Criar GraphRAG com embeddings para classificação semântica
            self.graph_rag = GraphRAGEngine(self.knowledge_graph, self.embeddings)
            
            # Inicializar classificador de intenção (pré-computa embeddings)
            self.graph_rag.initialize_classifier()
            
            # Inicializar extrator de relações (usa o mesmo LLM)
            self.relation_extractor = RelationExtractor(llm=self.llm)
            self.graph_enricher = KnowledgeGraphEnricher(self.knowledge_graph, self.relation_extractor)
            
            print("Knowledge Graph inicializado!")
        except Exception as e:
            print(f"Erro ao inicializar Knowledge Graph: {e}")
            self.knowledge_graph = None
            self.graph_rag = None
            self.relation_extractor = None
            self.graph_enricher = None
    
    def _apply_changes(self, changes: Dict, current_files: Dict):
        if changes["deleted"]:
            print(f"Removendo {len(changes['deleted'])} arquivos deletados...")
            for filepath in changes["deleted"]:
                results = self.db.get(where={"source": filepath})
                if results and results['ids']:
                    self.db._collection.delete(ids=results['ids'])
        
        files_to_update = changes["new"] + changes["modified"]
        if files_to_update:
            print(f"Atualizando {len(files_to_update)} arquivos...")
            
            for filepath in changes["modified"]:
                results = self.db.get(where={"source": filepath})
                if results and results['ids']:
                    self.db._collection.delete(ids=results['ids'])
            
            new_docs = []
            for filepath in files_to_update:
                new_docs.extend(parse_file(filepath))
            
            if new_docs:
                chunker = SemanticChunker(
                    max_chunk_size=self.config.CHUNK_SIZE,
                    chunk_overlap=self.config.CHUNK_OVERLAP
                )
                splits = chunker.split_documents(new_docs)
                self.db.add_documents(splits)
                print(f"Adicionados {len(splits)} novos chunks.")
        
        self._save_index({"files": current_files})
    
    def _load_db(self):
        self.db = Chroma(
            persist_directory=self.config.PERSIST_DIR,
            embedding_function=self.embeddings
        )
        self._setup_retriever()
        self._setup_chain()
    
    def _setup_retriever(self):
        self.retriever = self.db.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": self.config.RETRIEVER_K,
                "fetch_k": self.config.RETRIEVER_K * 2,
                "lambda_mult": 0.7
            }
        )
    
    def _setup_chain(self):
        template = """Voce e o Assistente Unifesp ICT. Responda APENAS em PORTUGUES BRASILEIRO usando o contexto abaixo:

{context}

Pergunta: {question}

Regras:
- Use APENAS informacoes do contexto
- Para disciplinas: cite nome, codigo, carga horaria e docentes quando disponivel
- Para regimentos: cite artigo e secao quando disponivel
- Se nao encontrar, diga claramente
- Seja direto e objetivo

Resposta:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        
        self.chain = (
            {"context": self.retriever | self._format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
    
    def _format_docs(self, docs) -> str:
        parts = []
        for doc in docs:
            tipo = doc.metadata.get('tipo_documento', 'documento')
            if tipo == 'disciplina':
                header = f"[Disciplina: {doc.metadata.get('disciplina', 'N/A')} - {doc.metadata.get('secao', '')}]"
            else:
                header = f"[{doc.metadata.get('documento', 'Documento')} - {doc.metadata.get('secao', '')}]"
            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)
    
    def enrich_graph_from_text(self, text: str, min_confidence: float = 0.7) -> Dict:
        """
        Extrai relações de um texto e adiciona ao Knowledge Graph.
        
        Args:
            text: Texto para extrair relações
            min_confidence: Confiança mínima (0.5 a 1.0)
            
        Returns:
            Estatísticas da extração
        """
        if not self.graph_enricher:
            return {"error": "Graph enricher não inicializado. Execute sync() primeiro."}
        
        added = self.graph_enricher.enrich_from_text(text, min_confidence)
        stats = self.graph_enricher.get_extraction_stats()
        stats['relations_added_now'] = added
        
        return stats
    
    def extract_relations(self, text: str, min_confidence: float = 0.6) -> List[Dict]:
        """
        Extrai relações de um texto sem adicionar ao grafo.
        Útil para preview/validação antes de enriquecer.
        
        Args:
            text: Texto para extrair relações
            min_confidence: Confiança mínima
            
        Returns:
            Lista de relações extraídas
        """
        if not self.relation_extractor:
            return []
        
        relations = self.relation_extractor.extract_from_text(text, min_confidence)
        return [
            {
                'subject': r.subject,
                'subject_type': r.subject_type,
                'relation': r.relation,
                'object': r.object,
                'object_type': r.object_type,
                'confidence': r.confidence
            }
            for r in relations
        ]
    
    def query(self, question: str) -> str:
        if not self.chain:
            self.sync()
        
        question_lower = question.lower()
        
        # 1. Obter contexto do GraphRAG (se disponível)
        graph_context = ""
        graph_query_type = None
        if self.graph_rag:
            should_use, query_type, termo = self.graph_rag.should_use_graph(question)
            if should_use:
                graph_query_type = query_type
                graph_response = self.graph_rag.query_graph(query_type, termo)
                if graph_response:
                    graph_context = f"\n\n{graph_response}\n"
        
        # 2. Para queries estruturadas, o GraphRAG já tem tudo - não precisa RAG tradicional
        graph_only_types = [
            # Docentes
            'docente_info', 'docente_areas', 'docente_disciplines', 
            'discipline_docentes', 'docentes_by_area', 'docente_leciona_disciplina',
            # Matriz curricular
            'disciplinas_termo', 'todos_termos_curso', 'matriz_info', 'eletivas_curso',
            # Cursos
            'listar_cursos', 'coordenador_curso',
            # Pré-requisitos
            'prerequisite_chain', 'dependents'
        ]
        
        # Termos que indicam que o grafo não tem a informação completa
        # e precisamos do RAG vetorial como fallback
        needs_rag_fallback = any(term in question_lower for term in [
            'sequencial', 'sequenciais', 'certificado', 'certificacao',
            'regulamento', 'norma', 'regimento', 'artigo', 'resolucao',
            'evacuacao', 'incendio', 'seguranca', 'faq', 'perguntas frequentes',
            # Nomes de cursos sequenciais específicos
            'fundamentos de ciência de dados', 'fundamentos de ciencia de dados',
            'métodos estatísticos', 'metodos estatisticos',
            'economia e mercados', 'química aplicada', 'quimica aplicada',
            'desenvolvimento de games', 'jogos digitais',
            # Detalhes de matriz curricular (documentos tem mais info que o grafo)
            'matriz curricular', 'grade curricular', 'carga horária total', 'carga horaria total',
            'primeiro termo', 'segundo termo', 'terceiro termo', 'quarto termo',
            'quinto termo', 'sexto termo', 'sétimo termo', 'oitavo termo', 'nono termo', 'décimo termo',
            '1º termo', '2º termo', '3º termo', '4º termo', '5º termo',
            '6º termo', '7º termo', '8º termo', '9º termo', '10º termo',
            '1o termo', '2o termo', '3o termo', '4o termo', '5o termo',
            'coordenador', 'coordenadora', 'vice-coordenador', 'vice-coordenadora',
            'informações sobre', 'informacoes sobre', 'detalhes do curso', 'visão geral',
            'engenharia de computação', 'engenharia de computacao',
            'ciência da computação', 'ciencia da computacao', 
            'engenharia de materiais', 'engenharia biomedica', 'engenharia biomédica',
            'biotecnologia', 'matemática computacional', 'matematica computacional'
        ])
        
        if graph_query_type in graph_only_types and graph_context and not needs_rag_fallback:
            # Usar apenas o contexto do GraphRAG para evitar confusão
            combined_context = graph_context
        else:
            # 3. Obter documentos do RAG tradicional
            targeted_docs = self._smart_retrieve(question, question_lower)
            
            # 4. Combinar contextos
            if targeted_docs:
                rag_context = self._format_docs(targeted_docs)
            else:
                # Fallback para retriever padrão
                docs = self.retriever.invoke(question)
                rag_context = self._format_docs(docs)
            
            combined_context = graph_context + rag_context
        
        # 5. SEMPRE passar pelo LLM para gerar resposta natural
        template = """Voce e o Assistente Unifesp ICT. Responda APENAS em PORTUGUES BRASILEIRO.

{context}

Pergunta: {question}

INSTRUCOES OBRIGATORIAS:
1. Use APENAS as informacoes presentes no contexto acima
2. NAO INVENTE disciplinas, emails, salas ou informacoes que nao estejam no contexto
3. Se houver listas, mantenha TODAS as informacoes listadas
4. Responda de forma natural e direta
5. Se a informacao nao estiver no contexto, diga que nao tem essa informacao

IMPORTANTE: Nao adicione disciplinas ou dados que nao foram explicitamente mencionados no contexto.

Resposta:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        
        return chain.invoke({"context": combined_context, "question": question})
    
    def _smart_retrieve(self, question: str, question_lower: str) -> List[Document]:
        # 1. Perguntas sobre regimentos/institucionais
        regimento_keywords = [
            'atividade complementar', 'atividades complementares', 'ac ', 'ace ',
            'horas complementares', 'eixo', 'carga horaria minima',
            'curso', 'cursos', 'graduacao', 'pos-graduacao', 'mestrado', 'doutorado',
            'regimento', 'regra', 'regulamento', 'norma', 'artigo',
            'campus', 'unifesp', 'ict', 'instituto', 'bct',
            'camara', 'congregacao', 'departamento', 'conselho',
            'eleicao', 'mandato', 'diretor', 'chefe',
            'extensao', 'cultura', 'biblioteca', 'sae', 'nae',
            'falta', 'perda de mandato', 'missao',
            # Matriz curricular e informações detalhadas de cursos
            'matriz curricular', 'grade curricular', 'grade de',
            'termo', 'semestre', 'primeiro termo', 'segundo termo', 
            'terceiro termo', 'quarto termo', 'quinto termo',
            '1º termo', '2º termo', '3º termo', '4º termo', '5º termo',
            '6º termo', '7º termo', '8º termo', '9º termo', '10º termo',
            'carga horaria total', 'total de creditos', 'coordenador',
            'certificacao', 'diploma', 'tcc', 'estagio supervisionado',
            'informações sobre o curso', 'informacoes sobre o curso',
            'disciplinas do curso', 'disciplinas de ec', 'disciplinas de bcc',
            'engenharia de computação', 'engenharia de computacao',
            'ciência da computação', 'ciencia da computacao',
            'engenharia de materiais', 'engenharia biomedica',
            'biotecnologia', 'matemática computacional', 'matematica computacional'
        ]
        
        if any(kw in question_lower for kw in regimento_keywords):
            docs = self._retrieve_regimento_docs(question_lower)
            if docs:
                return docs
        
        # 2. Perguntas sobre disciplina
        disciplina = self._extract_discipline_name(question)
        if disciplina:
            docs = self._retrieve_discipline_docs(disciplina, question_lower)
            if docs:
                return docs
        
        return []
    
    def _extract_discipline_name(self, query: str) -> Optional[str]:
        # Primeiro, tentar detectar siglas (2-5 letras maiúsculas)
        sigla_patterns = [
            r'\b([A-Z]{2,5})\b',  # Sigla em maiúsculas isolada
            r'(?:disciplina|matéria|cadeira)\s+([A-Z]{2,5})\b',  # disciplina SO
            r'(?:de|da|do|em|sobre)\s+([A-Z]{2,5})\b',  # sobre IA
        ]
        
        for pattern in sigla_patterns:
            matches = re.findall(pattern, query)
            for sigla in matches:
                # Ignorar palavras comuns que podem parecer siglas
                if sigla.upper() not in ['DE', 'DA', 'DO', 'NA', 'NO', 'EM', 'SE', 'OU', 'E', 'A', 'O', 'OS', 'AS']:
                    # Verificar se é uma sigla válida no banco
                    if self._is_valid_sigla(sigla.upper()):
                        return f"SIGLA:{sigla.upper()}"
        
        patterns = [
            r'quem\s+(?:leciona|da|ensina|ministra)\s+([A-Za-z][^?.,!]+)',
            r'professor(?:es)?\s+(?:de|da|do)\s+([A-Za-z][^?.,!]+)',
            r'carga\s+horaria\s+(?:de|da|do)\s+([A-Za-z][^?.,!]+)',
            r'pre[-\s]?requisitos?\s+(?:de|da|do|para)\s+([A-Za-z][^?.,!]+)',
            r'ementa\s+(?:de|da|do)\s+([A-Za-z][^?.,!]+)',
            r'sobre\s+(?:a\s+disciplina\s+)?([A-Za-z][^?.,!]+)',
            r'(?:a\s+)?disciplina\s+([A-Za-z][^?.,!]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                disciplina = match.group(1).strip()
                disciplina = re.sub(r'[\?.,!]+$', '', disciplina).strip()
                disciplina = re.sub(r'\s+(da|de|do|na|no|em|para)$', '', disciplina, flags=re.IGNORECASE).strip()
                if len(disciplina) >= 3:
                    return disciplina
        
        return None
    
    def _is_valid_sigla(self, sigla: str) -> bool:
        """Verifica se a sigla existe no banco de dados."""
        if not self.db:
            return False
        try:
            all_results = self.db.get()
            for meta in all_results.get('metadatas', []):
                if meta.get('sigla', '').upper() == sigla.upper():
                    return True
        except Exception as e:
            # Log para debug, mas não falha a operação
            print(f"[WARNING] Erro ao verificar sigla {sigla}: {e}")
        return False
    
    def _retrieve_discipline_docs(self, disciplina: str, question_lower: str) -> List[Document]:
        try:
            # Verificar se é uma busca por sigla
            if disciplina.startswith('SIGLA:'):
                sigla = disciplina.replace('SIGLA:', '')
                results = self._search_by_sigla(sigla)
            else:
                results = self.db.get(where={"disciplina": disciplina})
                
                if not results.get('ids'):
                    results = self._fuzzy_discipline_search(disciplina)
            
            if not results.get('ids'):
                return []
            
            docs = [
                Document(page_content=doc_text, metadata=meta)
                for doc_text, meta in zip(results.get('documents', []), results.get('metadatas', []))
            ]
            
            if 'docente' in question_lower or 'professor' in question_lower or 'quem leciona' in question_lower:
                filtered = [d for d in docs if d.metadata.get('secao') == 'docentes']
                if filtered:
                    return filtered[:3]
            
            if 'pre-requisito' in question_lower or 'prerequisito' in question_lower or 'requisito' in question_lower:
                filtered = [d for d in docs if d.metadata.get('secao') == 'pre_requisitos']
                if filtered:
                    return filtered[:3]
            
            if 'carga' in question_lower or 'hora' in question_lower:
                filtered = [d for d in docs if d.metadata.get('secao') == 'carga_horaria']
                if filtered:
                    return filtered[:3]
            
            if 'ementa' in question_lower or 'conteudo' in question_lower:
                filtered = [d for d in docs if d.metadata.get('secao') == 'ementa']
                if filtered:
                    return filtered[:3]
            
            if 'bibliografia' in question_lower or 'livro' in question_lower:
                filtered = [d for d in docs if 'bibliografia' in d.metadata.get('secao', '')]
                if filtered:
                    return filtered[:4]
            
            info_geral = [d for d in docs if d.metadata.get('secao') == 'info_geral']
            outros = [d for d in docs if d.metadata.get('secao') != 'info_geral'][:4]
            return info_geral + outros
            
        except Exception as e:
            print(f"Erro ao buscar disciplina: {e}")
            return []
    
    def _search_by_sigla(self, sigla: str) -> Dict:
        """Busca disciplinas pela sigla."""
        all_results = self.db.get()
        
        matching_ids = []
        matching_metadatas = []
        matching_documents = []
        
        sigla_upper = sigla.upper()
        
        for i, meta in enumerate(all_results.get('metadatas', [])):
            meta_sigla = meta.get('sigla', '').upper()
            if meta_sigla == sigla_upper:
                matching_ids.append(all_results['ids'][i])
                matching_metadatas.append(all_results['metadatas'][i])
                matching_documents.append(all_results['documents'][i])
        
        return {
            'ids': matching_ids,
            'metadatas': matching_metadatas,
            'documents': matching_documents
        }
    
    def _fuzzy_discipline_search(self, disciplina: str) -> Dict:
        all_results = self.db.get()
        
        matches_with_score = []
        disciplina_lower = disciplina.lower().strip()
        disciplina_normalized = re.sub(r'(\w+)s\b', r'\1', disciplina_lower)
        
        palavras_chave = [p for p in disciplina_normalized.split() if len(p) > 2]
        
        for i, meta in enumerate(all_results.get('metadatas', [])):
            disciplina_db = meta.get('disciplina', '')
            sigla_db = meta.get('sigla', '').lower()
            if not disciplina_db:
                continue
            
            disciplina_db_lower = disciplina_db.lower()
            disciplina_db_normalized = re.sub(r'(\w+)s\b', r'\1', disciplina_db_lower)
                        
            score = 0
            
            # Verificar match por sigla (case-insensitive)
            if sigla_db and disciplina_lower == sigla_db:
                score = 100
            elif disciplina_lower == disciplina_db_lower or disciplina_normalized == disciplina_db_normalized:
                score = 100
            elif disciplina_lower in disciplina_db_lower or disciplina_normalized in disciplina_db_normalized:
                score = 90
            elif disciplina_db_lower in disciplina_lower or disciplina_db_normalized in disciplina_normalized:
                score = 85
            else:
                palavras_db = [p for p in disciplina_db_normalized.split() if len(p) > 2]
                if palavras_chave and palavras_db:
                    matches_exatos = sum(1 for p in palavras_chave if p in palavras_db)
                    matches_parciais = sum(1 for p in palavras_chave if any(p in pd or pd in p for pd in palavras_db)) - matches_exatos
                    total_palavras = max(len(palavras_chave), len(palavras_db))
                    score = (matches_exatos * 15 + matches_parciais * 5) / total_palavras * 10
            
            if score >= 50:
                matches_with_score.append({
                    'index': i,
                    'score': score,
                    'disciplina': disciplina_db
                })
        
        matches_with_score.sort(key=lambda x: x['score'], reverse=True)
        
        top_disciplinas = set()
        for m in matches_with_score:
            if m['score'] >= 80 or len(top_disciplinas) < 2:
                top_disciplinas.add(m['disciplina'])
            if len(top_disciplinas) >= 3:
                break
        
        matching_ids = []
        matching_metadatas = []
        matching_documents = []
        
        for m in matches_with_score:
            if m['disciplina'] in top_disciplinas:
                idx = m['index']
                matching_ids.append(all_results['ids'][idx])
                matching_metadatas.append(all_results['metadatas'][idx])
                matching_documents.append(all_results['documents'][idx])
        
        return {
                            'ids': matching_ids,
                            'metadatas': matching_metadatas,
                            'documents': matching_documents
                        }
                
    def _retrieve_regimento_docs(self, question_lower: str) -> List[Document]:
        try:
            all_results = self.db.get()
            
            regimento_docs = []
            scores = []
            
            # Palavras-chave com pesos
            keywords = {
                'atividades complementares': 10, 'atividade complementar': 10,
                'carga horaria': 8, 'horas': 5, '312': 15,
                'ac ': 6, 'ace ': 6, 'eixo': 6, 'eixos': 6,
                'curso': 3, 'graduacao': 3, 'cursos': 3, 'bct': 4,
                'pos-graduacao': 4, 'mestrado': 4, 'doutorado': 4,
                'regimento': 4, 'regulamento': 4, 'regra': 3, 'artigo': 3,
                'camara': 3, 'congregacao': 3, 'departamento': 2, 'conselho': 2,
                'sae': 5, 'biblioteca': 3, 'extensao': 3, 'nae': 4,
                'missao': 3, 'objetivo': 2, 'campus': 2, 'unifesp': 2,
                # Matriz curricular keywords
                'matriz': 5, 'semestre': 4, 'termo': 4, 'disciplina': 3,
                'coordenador': 5, 'creditos': 3, 'primeiro': 3, 'segundo': 3
            }
            
            # Keywords específicos para detectar perguntas sobre matrizes curriculares
            matriz_keywords = ['matriz', 'termo', 'semestre', 'primeiro', 'segundo', 
                             'terceiro', 'quarto', 'quinto', 'sexto', 'sétimo', 'oitavo',
                             'coordenador', 'grade', 'disciplinas do curso', 'engenharia de computação',
                             'ciência da computação', 'biotecnologia', 'engenharia de materiais',
                             'matemática computacional', 'engenharia biomédica']
            is_matriz_question = any(kw in question_lower for kw in matriz_keywords)
            
            for i, doc_text in enumerate(all_results.get('documents', [])):
                meta = all_results['metadatas'][i]
                
                # Aceitar documentos institucionais OU matrizes curriculares
                tipo_doc = meta.get('tipo_documento', '')
                tipo = meta.get('tipo', '')
                
                # Se é pergunta sobre matriz, priorizar matrizes curriculares
                if is_matriz_question:
                    if tipo != 'matriz_curricular' and tipo_doc != 'institucional':
                        continue
                else:
                    if tipo_doc != 'institucional' and tipo != 'matriz_curricular':
                        continue
                
                doc_lower = doc_text.lower()
                score = 0
                
                # Calcular score baseado em keywords
                for kw, weight in keywords.items():
                    if kw in question_lower and kw in doc_lower:
                        score += weight
                
                # Bonus grande para FAQs
                if meta.get('secao') == 'faq':
                    score += 10
                    
                    # Bonus extra se pergunta do FAQ contem palavras da questao
                    if 'pergunta' in doc_lower:
                        palavras_pergunta = [p for p in question_lower.split() if len(p) > 3]
                        for palavra in palavras_pergunta:
                            if palavra in doc_lower:
                                score += 5
                
                # Bonus para objetivo do documento
                if meta.get('secao') == 'objetivo':
                    score += 3
                
                # Bonus para matrizes curriculares
                if tipo == 'matriz_curricular':
                    secao = meta.get('secao', '')
                    sigla = meta.get('sigla', '').lower()
                    
                    # Se pergunta menciona termo/semestre específico, priorizar esses docs
                    if 'termo_' in secao:
                        termo_num = secao.replace('termo_', '')
                        termos_map = {
                            'primeiro': '1', 'primeiro termo': '1', '1': '1', '1º': '1', '1o': '1', 'termo 1': '1',
                            'segundo': '2', 'segundo termo': '2', '2': '2', '2º': '2', '2o': '2', 'termo 2': '2',
                            'terceiro': '3', 'terceiro termo': '3', '3': '3', '3º': '3', '3o': '3', 'termo 3': '3',
                            'quarto': '4', 'quarto termo': '4', '4': '4', '4º': '4', '4o': '4', 'termo 4': '4',
                            'quinto': '5', 'quinto termo': '5', '5': '5', '5º': '5', '5o': '5', 'termo 5': '5',
                            'sexto': '6', 'sexto termo': '6', '6': '6', '6º': '6', '6o': '6', 'termo 6': '6',
                            'sétimo': '7', 'setimo': '7', 'sétimo termo': '7', '7': '7', '7º': '7', '7o': '7', 'termo 7': '7',
                            'oitavo': '8', 'oitavo termo': '8', '8': '8', '8º': '8', '8o': '8', 'termo 8': '8',
                            'nono': '9', 'nono termo': '9', '9': '9', '9º': '9', '9o': '9', 'termo 9': '9',
                            'décimo': '10', 'decimo': '10', 'décimo termo': '10', '10': '10', '10º': '10', '10o': '10', 'termo 10': '10'
                        }
                        for termo_word, termo_val in termos_map.items():
                            if termo_word in question_lower and termo_val == termo_num:
                                score += 20  # Alto bonus para termo correto
                    
                    # Se pergunta menciona sigla do curso, priorizar
                    if sigla and sigla in question_lower:
                        score += 15
                    
                    # Se pergunta menciona nome do curso
                    titulo = meta.get('titulo', '').lower()
                    if 'engenharia de computa' in question_lower and 'engenharia de computa' in titulo:
                        score += 15
                    if 'ciência da computa' in question_lower and 'ciência da computa' in titulo:
                        score += 15
                    if 'ciencia da computa' in question_lower:
                        score += 15
                    if 'biotecnologia' in question_lower and 'biotecnologia' in titulo:
                        score += 15
                    
                    # Resumo sempre tem pontos para perguntas gerais
                    if secao == 'resumo':
                        score += 5
                
                if score > 0:
                    regimento_docs.append(Document(page_content=doc_text, metadata=meta))
                    scores.append(score)
            
            if regimento_docs:
                sorted_docs = [doc for _, doc in sorted(zip(scores, regimento_docs), key=lambda x: x[0], reverse=True)]
                return sorted_docs[:8]
            
            return []
            
        except Exception as e:
            print(f"Erro ao buscar regimentos: {e}")
            return []
    
    def _query_with_context(self, question: str, docs: List[Document]) -> str:
        from langchain_core.runnables import RunnableLambda
        
        template = """Voce e o Assistente Unifesp ICT. Responda APENAS em PORTUGUES BRASILEIRO usando o contexto abaixo:

{context}

Pergunta: {question}

Regras:
- Use APENAS informacoes do contexto fornecido
- Para disciplinas: cite nome, codigo, docentes, carga horaria e pre-requisitos quando relevante
- Para regimentos: cite artigo e secao quando disponivel
- Se nao encontrar a informacao, diga claramente
- Seja direto e objetivo

Resposta:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        context = self._format_docs(docs)
        
        chain = (
            {"context": RunnableLambda(lambda x: context), "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        return chain.invoke(question)
    
    def list_sources(self) -> Dict[str, int]:
        if not self.db:
            self.sync()
        
        results = self.db.get()
        counts = {"disciplinas": 0, "regimentos": 0}
        seen = set()
        
        for meta in results.get('metadatas', []):
            source = meta.get('source', '')
            if source in seen:
                continue
            seen.add(source)
            if 'disciplinas' in source:
                counts["disciplinas"] += 1
            elif 'regimentos' in source:
                counts["regimentos"] += 1
        
        return counts
