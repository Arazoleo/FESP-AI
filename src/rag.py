import os
import json
import hashlib
import warnings
from pathlib import Path
from typing import Dict, List, Optional

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
from .parsers import parse_file


class RAGUnifesp:
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        ollama_base_url = self.config.OLLAMA_BASE_URL
        keep_alive_seconds = 600
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
            for json_file in Path(directory).glob("*.json"):
                filepath = str(json_file)
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
            return False
        
        if force or not db_exists:
            print("Recriando banco vetorial...")
            all_docs = []
            for filepath in current_files:
                all_docs.extend(parse_file(filepath))
            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.CHUNK_SIZE,
                chunk_overlap=self.config.CHUNK_OVERLAP
            )
            splits = splitter.split_documents(all_docs)
            
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
        return True
    
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
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.config.CHUNK_SIZE,
                    chunk_overlap=self.config.CHUNK_OVERLAP
                )
                splits = splitter.split_documents(new_docs)
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
    
    def _extract_discipline_name(self, query: str) -> Optional[str]:
        import re
        
        match_question_part = re.search(r'(?:Pergunta atual:\s*)(.*)', query, re.IGNORECASE)
        if match_question_part:
            clean_query = match_question_part.group(1).strip()
        else:
            clean_query = query
        
        patterns = [
            r'docentes?\s+de\s+([A-Za-zÀ-Úà-ú][^?]+)(?:\?|$|\.|,|!)',
            r'carga\s+horaria\s+de\s+([A-Za-zÀ-Úà-ú][^?]+)(?:\?|$|\.|,|!)',
            r'pré[-\s]?requisitos?\s+(?:de|da)\s+([A-Za-zÀ-Úà-ú][^?]+)(?:\?|$|\.|,|!)',
            r'ementa\s+de\s+([A-Za-zÀ-Úà-ú][^?]+)(?:\?|$|\.|,|!)',
            r'e\s+os\s+(?:de\s+|pré[-\s]?requisitos\s+de\s+|docentes?\s+de\s+)([A-Za-zÀ-Úà-ú][^?]+)(?:\?|$|\.|,|!)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, clean_query, re.IGNORECASE)
            if match:
                disciplina = match.group(1).strip()
                disciplina = disciplina.rstrip('?.,!')
                if len(disciplina) >= 3:
                    return disciplina
        
        return None
    
    def _setup_retriever(self):
        self.retriever = self.db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.config.RETRIEVER_K}
        )
    
    def _setup_chain(self):
        template = """Você é o Assistente Unifesp ICT. CRÍTICO: Você DEVE SEMPRE responder em PORTUGUÊS BRASILEIRO (pt-BR). NUNCA responda em inglês, espanhol ou qualquer outro idioma. Responda APENAS com o contexto abaixo:

{context}

Pergunta: {question}

Regras OBRIGATÓRIAS:
- LÍNGUA: Você DEVE responder SEMPRE em PORTUGUÊS BRASILEIRO. Esta é uma regra ABSOLUTA e não negociável.
- Use APENAS informacoes do contexto
- Para perguntas sobre disciplinas: procure primeiro nos documentos com tipo_documento='disciplina' e secao='info_geral'
- Disciplinas: SEMPRE cite nome, codigo, carga horaria e docentes quando disponivel
- Se a pergunta menciona uma disciplina especifica (ex: "Circuitos Digitais"), priorize documentos dessa disciplina
- Para perguntas sobre cursos de graduação: procure no artigo 23 do regimento interno ou em FAQs sobre cursos
- Se a pergunta pede lista de cursos e menciona "tirando o BCT" ou "exceto BCT" ou "além do BCT", liste TODOS os cursos EXCETO o "Bacharelado Interdisciplinar em Ciência e Tecnologia"
- Se a pergunta pede lista de cursos sem exclusões, liste TODOS os cursos mencionados no contexto
- Regimentos: cite artigo e secao quando disponivel
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
        
        if 'curso' in question.lower() and ('graduação' in question.lower() or 'formação' in question.lower()):
            try:
                all_results = self.db.get()
                all_metadatas = all_results.get('metadatas', [])
                all_documents = all_results.get('documents', [])
                all_ids = all_results.get('ids', [])
                
                course_docs = []
                for i, doc_text in enumerate(all_documents):
                    meta = all_metadatas[i]
                    if (meta.get('secao') == 'faq' and 'curso' in doc_text.lower() and 'graduação' in doc_text.lower()) or \
                       (meta.get('secao') == 'artigo' and '23' in doc_text and 'curso' in doc_text.lower()):
                        from langchain_core.documents import Document
                        course_docs.append(Document(
                            page_content=doc_text,
                            metadata=meta
                        ))
                
                if course_docs:
                    seen_content = set()
                    unique_docs = []
                    for doc in course_docs:
                        content_hash = hash(doc.page_content[:200])
                        if content_hash not in seen_content:
                            seen_content.add(content_hash)
                            unique_docs.append(doc)
                    course_docs = unique_docs
                    
                    import re
                    all_courses = []
                    for doc in course_docs:
                        matches = re.findall(r'-\s*(Bacharelado[^\n]+)', doc.page_content)
                        if matches:
                            all_courses.extend([m.strip() for m in matches])
                        if 'Bacharelado' in doc.page_content:
                            faq_match = re.search(r'cursos de graduação:\s*([^\.]+)', doc.page_content, re.IGNORECASE)
                            if faq_match:
                                courses_str = faq_match.group(1)
                                courses = []
                                parts = courses_str.split(',')
                                for part in parts:
                                    part = part.strip()
                                    if ' e ' in part and part.startswith('Bacharelado'):
                                        sub_parts = re.split(r'\s+e\s+(?=Bacharelado)', part)
                                        courses.extend([p.strip() for p in sub_parts])
                                    else:
                                        courses.append(part)
                                all_courses.extend(courses)
                    
                    unique_courses = []
                    seen = set()
                    for course in all_courses:
                        course_clean = course.strip().rstrip('.')
                        if course_clean and course_clean not in seen:
                            seen.add(course_clean)
                            unique_courses.append(course_clean)
                    
                    exclude_bct = 'tirando' in question.lower() or 'exceto' in question.lower() or 'além' in question.lower()
                    if exclude_bct:
                        filtered_courses = [c for c in unique_courses if 'Interdisciplinar' not in c and 'BCT' not in c.upper()]
                        if filtered_courses:
                            return f"Os cursos específicos de formação na UNIFESP (excluindo o BCT) são:\n\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(filtered_courses))
                    
                    if unique_courses:
                        return f"Os cursos de graduação do Campus São José dos Campos são:\n\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(unique_courses))
            except Exception as e:
                pass
        
        disciplina = self._extract_discipline_name(question)
        discipline_docs = []
        
        if disciplina:
            try:
                results = self.db.get(where={"disciplina": disciplina})
                
                if not results.get('ids'):
                    all_results = self.db.get()
                    all_metadatas = all_results.get('metadatas', [])
                    all_documents = all_results.get('documents', [])
                    all_ids = all_results.get('ids', [])
                    
                    matching_ids = []
                    matching_metadatas = []
                    matching_documents = []
                    
                    disciplina_lower = disciplina.lower()
                    import re
                    disciplina_normalized = re.sub(r'(\w+)s\b', r'\1', disciplina_lower)
                    
                    for i, meta in enumerate(all_metadatas):
                        disciplina_db = meta.get('disciplina', '')
                        disciplina_db_lower = disciplina_db.lower()
                        disciplina_db_normalized = re.sub(r'(\w+)s\b', r'\1', disciplina_db_lower)
                        
                        palavras_chave = [p for p in disciplina_normalized.split() if len(p) > 3]
                        palavras_db = [p for p in disciplina_db_normalized.split() if len(p) > 3]
                        
                        match_score = sum(1 for p in palavras_chave if p in palavras_db or any(p in pd or pd in p for pd in palavras_db))
                        
                        if (disciplina_lower in disciplina_db_lower or 
                            disciplina_db_lower in disciplina_lower or
                            disciplina_normalized in disciplina_db_normalized or
                            disciplina_db_normalized in disciplina_normalized or
                            match_score >= len(palavras_chave) * 0.7):
                            matching_ids.append(all_ids[i])
                            matching_metadatas.append(meta)
                            matching_documents.append(all_documents[i])
                    
                    if matching_ids:
                        results = {
                            'ids': matching_ids,
                            'metadatas': matching_metadatas,
                            'documents': matching_documents
                        }
                
                if results.get('ids'):
                    from langchain_core.documents import Document
                    metadatas = results.get('metadatas', [])
                    documents = results.get('documents', [])
                    
                    disciplina_lower = disciplina.lower()
                    for i, doc_text in enumerate(documents):
                        if i < len(metadatas):
                            discipline_docs.append(Document(
                                page_content=doc_text,
                                metadata=metadatas[i]
                            ))
                    
                    discipline_docs.sort(key=lambda d: (
                        0 if d.metadata.get('disciplina', '').lower() == disciplina_lower else 1,
                        d.metadata.get('secao') != 'info_geral'
                    ))
                    
                    if 'docente' in question.lower() or 'carga' in question.lower():
                        info_geral = [d for d in discipline_docs if d.metadata.get('secao') == 'info_geral' and d.metadata.get('disciplina', '').lower() == disciplina_lower]
                        if info_geral:
                            discipline_docs = info_geral[:1]
                        else:
                            exatos = [d for d in discipline_docs if d.metadata.get('disciplina', '').lower() == disciplina_lower]
                            if exatos:
                                discipline_docs = exatos[:1]
                    
                    if 'pré' in question.lower() or 'prerequisito' in question.lower() or 'requisito' in question.lower():
                        ementa_docs = [d for d in discipline_docs if d.metadata.get('secao') == 'ementa' and ('pre_requisito' in d.page_content.lower() or 'pré-requisito' in d.page_content.lower())]
                        if ementa_docs:
                            discipline_docs = ementa_docs[:self.config.RETRIEVER_K]
                        else:
                            pre_requisitos_docs = [d for d in discipline_docs if 'pre_requisito' in d.page_content.lower() or 'pré-requisito' in d.page_content.lower()]
                            if pre_requisitos_docs:
                                discipline_docs = pre_requisitos_docs[:self.config.RETRIEVER_K]
            except Exception as e:
                pass
        
        if 'curso' in question.lower() and ('graduação' in question.lower() or 'formação' in question.lower()):
            try:
                all_results = self.db.get()
                all_metadatas = all_results.get('metadatas', [])
                all_documents = all_results.get('documents', [])
                all_ids = all_results.get('ids', [])
                
                course_docs = []
                for i, doc_text in enumerate(all_documents):
                    meta = all_metadatas[i]
                    if (meta.get('secao') == 'faq' and 'curso' in doc_text.lower() and 'graduação' in doc_text.lower()) or \
                       (meta.get('secao') == 'artigo' and '23' in doc_text and 'curso' in doc_text.lower()):
                        from langchain_core.documents import Document
                        course_docs.append(Document(
                            page_content=doc_text,
                            metadata=meta
                        ))
                
                if course_docs:
                    seen_content = set()
                    unique_docs = []
                    for doc in course_docs:
                        content_hash = hash(doc.page_content[:200])
                        if content_hash not in seen_content:
                            seen_content.add(content_hash)
                            unique_docs.append(doc)
                    course_docs = unique_docs
                    
                    import re
                    all_courses = []
                    for doc in course_docs:
                        matches = re.findall(r'-\s*(Bacharelado[^\n]+)', doc.page_content)
                        if matches:
                            all_courses.extend([m.strip() for m in matches])
                        if 'Bacharelado' in doc.page_content:
                            faq_match = re.search(r'cursos de graduação:\s*([^\.]+)', doc.page_content, re.IGNORECASE)
                            if faq_match:
                                courses_str = faq_match.group(1)
                                courses = []
                                parts = courses_str.split(',')
                                for part in parts:
                                    part = part.strip()
                                    if ' e ' in part and part.startswith('Bacharelado'):
                                        sub_parts = re.split(r'\s+e\s+(?=Bacharelado)', part)
                                        courses.extend([p.strip() for p in sub_parts])
                                    else:
                                        courses.append(part)
                                all_courses.extend(courses)
                    
                    unique_courses = []
                    seen = set()
                    for course in all_courses:
                        course_clean = course.strip().rstrip('.')
                        if course_clean and course_clean not in seen:
                            seen.add(course_clean)
                            unique_courses.append(course_clean)
                    
                    exclude_bct = 'tirando' in question.lower() or 'exceto' in question.lower() or 'além' in question.lower()
                    if exclude_bct:
                        filtered_courses = [c for c in unique_courses if 'Interdisciplinar' not in c and 'BCT' not in c.upper()]
                        if filtered_courses:
                            return f"Os cursos específicos de formação na UNIFESP (excluindo o BCT) são:\n\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(filtered_courses))
                    
                    if unique_courses:
                        return f"Os cursos de graduação do Campus São José dos Campos são:\n\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(unique_courses))
                    
                    from langchain_core.runnables import RunnableLambda
                    from langchain_core.prompts import ChatPromptTemplate
                    from langchain_core.output_parsers import StrOutputParser
                    
                    template = """Assistente Unifesp ICT. Responda APENAS com o contexto abaixo:

{context}

Pergunta: {question}

Regras:
- Use APENAS informacoes do contexto
- Para perguntas sobre cursos de graduação: use as informações do artigo 23 do regimento interno
- Se a pergunta pede lista de cursos e menciona "tirando o BCT" ou "exceto BCT" ou "além do BCT", liste TODOS os cursos EXCETO o "Bacharelado Interdisciplinar em Ciência e Tecnologia" ou "BCT"
- Se a pergunta pede lista de cursos sem exclusões, liste TODOS os cursos mencionados no contexto
- Regimentos: cite artigo e secao quando disponivel
- Se nao encontrar, diga claramente
- Seja direto e objetivo

Resposta:"""
                    
                    prompt = ChatPromptTemplate.from_template(template)
                    context = self._format_docs(course_docs[:5])
                    
                    chain = (
                        {"context": RunnableLambda(lambda x: context), "question": RunnablePassthrough()}
                        | prompt
                        | self.llm
                        | StrOutputParser()
                    )
                    return chain.invoke(question)
            except Exception as e:
                pass
        
        if discipline_docs:
            from langchain_core.runnables import RunnableLambda
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            template = """Assistente Unifesp ICT. Responda APENAS com o contexto abaixo:

{context}

Pergunta: {question}

Regras:
- Use APENAS informacoes do contexto
- Disciplinas: SEMPRE cite nome, codigo, carga horaria e docentes quando disponivel
- Se nao encontrar, diga claramente
- Seja direto e objetivo

Resposta:"""
            
            prompt = ChatPromptTemplate.from_template(template)
            context = self._format_docs(discipline_docs)
            
            chain = (
                {"context": RunnableLambda(lambda x: context), "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
            return chain.invoke(question)
        
        return self.chain.invoke(question)
    
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

