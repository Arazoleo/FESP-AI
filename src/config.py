import os
from pathlib import Path


class Config:
    # Modelo mais leve e rápido (3B vs 7B = ~2x mais rápido)
    MODEL_NAME = "qwen2.5:3b"
    EMBEDDING_MODEL = "mxbai-embed-large"
    PERSIST_DIR = "./chroma_db_unifesp"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", None)
    
    SOURCES = {
        "disciplinas": "./markdown_disciplinas",
        "regimentos": "./markdown_regimentos"
    }
    
    # Diretórios para Knowledge Graph
    DISCIPLINAS_DIR = "./markdown_disciplinas"
    REGIMENTOS_DIR = "./markdown_regimentos"
    DOCENTES_DIR = "./markdown_docentes"
    
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

