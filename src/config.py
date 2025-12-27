import os
from pathlib import Path


class Config:
    # Modelos podem ser configurados via variáveis de ambiente
    # Exemplo: MODEL_NAME=qwen2.5:3b docker-compose up
    # Testando modelos mais leves para melhor performance
    MODEL_NAME = os.getenv("MODEL_NAME", "mistral:7b-instruct-q4_K_M")  # Modelo quantizado - bom equilíbrio velocidade/qualidade
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")  # Melhor qualidade (1024 dims)
    PERSIST_DIR = "./chroma_db_unifesp"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    SOURCES = {
        "disciplinas": "./jsons_disciplinas",
        "regimentos": "./jsons_regimentos"
    }
    
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    RETRIEVER_K = 15  # Número de documentos a recuperar (aumentado para melhorar recall)
    
    @classmethod
    def get_index_path(cls) -> str:
        return str(Path(cls.PERSIST_DIR) / "index.json")

