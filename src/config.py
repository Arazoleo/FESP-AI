import os
from pathlib import Path


class Config:
    MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:31b-cloud")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
    PERSIST_DIR = "./chroma_db_unifesp"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", None)

    HUMANIZE_KG = os.getenv("FESPAI_HUMANIZE_KG", "0") == "1"
    
    SOURCES = {
        "disciplinas": "./markdown_disciplinas",
        "regimentos": "./markdown_regimentos",
        "cursos": "./markdown_cursos"
    }
    
    DISCIPLINAS_DIR = "./markdown_disciplinas"
    REGIMENTOS_DIR = "./markdown_regimentos"
    DOCENTES_DIR = "./markdown_docentes"
    CURSOS_DIR = "./markdown_cursos"
    
    CHUNK_SIZE = 1500
    CHUNK_OVERLAP = 150
    
    RETRIEVER_K = 10
    
    @classmethod
    def get_index_path(cls) -> str:
        return str(Path(cls.PERSIST_DIR) / "index.json")
