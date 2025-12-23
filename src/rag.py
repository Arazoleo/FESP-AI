import os
import json
import hashlib
import warnings
from pathlib import Path
from typing import Dict, List

# Suprimir warnings de depreciação
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from .config import Config
from .parsers import parse_file


class RAGUnifesp:
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.llm = OllamaLLM(model=self.config.MODEL_NAME)
        self.embeddings = OllamaEmbeddings(model=self.config.EMBEDDING_MODEL)
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
    
    def _setup_retriever(self):
        self.retriever = self.db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.config.RETRIEVER_K}
        )
    
    def _setup_chain(self):
        template = """Voce e um assistente da Unifesp ICT em Sao Jose dos Campos.
Responda baseado APENAS no contexto abaixo:

{context}

Pergunta: {question}

Instrucoes:
- Use as informacoes do contexto
- Para disciplinas: cite nome, codigo, carga horaria
- Para regimentos: cite artigo e secao
- Se nao encontrar a informacao, diga claramente
- Seja objetivo e direto

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

