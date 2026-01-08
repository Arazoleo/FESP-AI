import os
import re
import json
import hashlib
import warnings
from pathlib import Path
from typing import Dict, List, Optional
from .knowledge_graph import KnowledgeGraph
from .graph_rag import GraphRAGEngine

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
        if ollama_base_url and ollama_base_url != "http://localhost:11434":
            self.llm = OllamaLLM(
                model=self.config.MODEL_NAME, 
                base_url=ollama_base_url,
                keep_alive=keep_alive_seconds
            )
            self.embeddings = OllamaEmbeddings(
                model=self.config.EMBEDDING_MODEL, 
                base_url=ollama_base_url,
                keep_alive=keep_alive_seconds
            )
        else:
            self.llm = OllamaLLM(model=self.config.MODEL_NAME, keep_alive=keep_alive_seconds)
            self.embeddings = OllamaEmbeddings(model=self.config.EMBEDDING_MODEL, keep_alive=keep_alive_seconds)
        
        self.db = None
        self.retriever = None
        self.chain = None
        self.knowledge_graph = None
        self.graph_rag = None
    
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
        """Inicializa o Knowledge Graph."""
        try:
            self.knowledge_graph = KnowledgeGraph()
            
            # Verificar se existe diretório de docentes
            docentes_dir = getattr(self.config, 'DOCENTES_DIR', None)
            if docentes_dir and os.path.exists(docentes_dir):
                self.knowledge_graph.build_from_directories(
                    str(self.config.DISCIPLINAS_DIR),
                    str(self.config.REGIMENTOS_DIR),
                    str(docentes_dir)
                )
            else:
                self.knowledge_graph.build_from_directories(
                    str(self.config.DISCIPLINAS_DIR),
                    str(self.config.REGIMENTOS_DIR)
                )
            
            self.graph_rag = GraphRAGEngine(self.knowledge_graph)
            print("Knowledge Graph inicializado!")
        except Exception as e:
            print(f"Erro ao inicializar Knowledge Graph: {e}")
            self.knowledge_graph = None
            self.graph_rag = None
    
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
    
    def query(self, question: str) -> str:
        if not self.chain:
            self.sync()
        
        question_lower = question.lower()
        
        # 1. Obter contexto do GraphRAG (se disponível)
        graph_context = ""
        if self.graph_rag:
            graph_response = self.graph_rag.get_graph_context(question)
            if graph_response:
                graph_context = f"\n\n[INFORMAÇÕES DO GRAFO DE CONHECIMENTO]\n{graph_response}\n"
        
        # 2. Obter documentos do RAG tradicional
        targeted_docs = self._smart_retrieve(question, question_lower)
        
        # 3. Combinar contextos
        if targeted_docs:
            rag_context = self._format_docs(targeted_docs)
        else:
            # Fallback para retriever padrão
            docs = self.retriever.invoke(question)
            rag_context = self._format_docs(docs)
        
        # 4. Contexto final combinado (GraphRAG + RAG)
        combined_context = graph_context + rag_context
        
        # 5. SEMPRE passar pelo LLM para gerar resposta natural
        template = """Voce e o Assistente Unifesp ICT. Responda APENAS em PORTUGUES BRASILEIRO.

{context}

Pergunta: {question}

REGRAS IMPORTANTES:
1. PRIORIDADE MAXIMA: Se houver [INFORMACOES DO GRAFO DE CONHECIMENTO], use-as como BASE PRINCIPAL da resposta
2. Use documentos adicionais apenas para complementar com detalhes (codigo, carga horaria, etc.)
3. NAO repita informacoes - seja conciso
4. Se a pergunta for sobre docentes/professores, use APENAS as disciplinas listadas no grafo de conhecimento
5. Seja direto, objetivo e amigavel

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
            'falta', 'perda de mandato', 'missao'
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
        except:
            pass
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
                'missao': 3, 'objetivo': 2, 'campus': 2, 'unifesp': 2
            }
            
            for i, doc_text in enumerate(all_results.get('documents', [])):
                meta = all_results['metadatas'][i]
                
                if meta.get('tipo_documento') != 'institucional':
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
