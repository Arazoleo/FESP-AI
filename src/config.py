import os
from pathlib import Path


class Config:
    MODEL_NAME =  "mistral:7b-instruct-q4_K_M"
    EMBEDDING_MODEL = "mxbai-embed-large"
    PERSIST_DIR = "./chroma_db_unifesp"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", None)
    
    SOURCES = {
        "disciplinas": "./jsons_disciplinas",
        "regimentos": "./jsons_regimentos"
    }
    
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    RETRIEVER_K = 15
    
    @classmethod
    def get_index_path(cls) -> str:
        return str(Path(cls.PERSIST_DIR) / "index.json")

