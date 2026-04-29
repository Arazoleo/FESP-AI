import os
from pathlib import Path


class Config:
    # Modelo de geração: use MODEL_NAME no .env ou docker para testar outro (ex.: llama3.1:70b na nuvem)
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-oss:120b-cloud")
    # Embeddings: mxbai-embed-large é ótimo para RAG; para multilíngue/PT-BR pode testar bge-m3 (ollama pull bge-m3)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
    PERSIST_DIR = "./chroma_db_unifesp"
    # URL do Ollama: local ou na nuvem (ex.: https://sua-instancia-ollama.com ou http://IP:11434)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", None)
    
    SOURCES = {
        "disciplinas": "./markdown_disciplinas",
        "regimentos": "./markdown_regimentos",
        "cursos": "./markdown_cursos"
    }
    
    # Diretórios para Knowledge Graph
    DISCIPLINAS_DIR = "./markdown_disciplinas"
    REGIMENTOS_DIR = "./markdown_regimentos"
    DOCENTES_DIR = "./markdown_docentes"
    CURSOS_DIR = "./markdown_cursos"
    
    # Chunking semântico otimizado
    # Documentos menores que CHUNK_SIZE são mantidos inteiros
    # Documentos maiores são divididos com overlap
    CHUNK_SIZE = 1500  # Aumentado para preservar mais documentos inteiros
    CHUNK_OVERLAP = 150  # Overlap menor já que documentos são semânticos
    
    # Retrieval
    RETRIEVER_K = 10  # Reduzido pois documentos são mais relevantes
    
    @classmethod
    def get_index_path(cls) -> str:
        return str(Path(cls.PERSIST_DIR) / "index.json")

