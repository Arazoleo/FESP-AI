import os
from pathlib import Path


class Config:
    # Modelo de geração: use MODEL_NAME no .env ou docker para testar outro (ex.: llama3.1:70b na nuvem)
    MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:31b-cloud")
    # Embeddings: mxbai-embed-large (1024d) é ótimo para RAG; alternativas:
    # embeddinggemma (768d), bge-m3 (multilíngue). Troque via EMBEDDING_MODEL no
    # .env/docker — NUNCA hardcoded, senão a env var do compose para de valer.
    # ATENÇÃO: trocar o modelo muda a dimensão dos vetores; o sync detecta e
    # reconstrói a collection automaticamente (demora alguns minutos).
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
    PERSIST_DIR = "./chroma_db_unifesp"
    # URL do Ollama: local ou na nuvem (ex.: https://sua-instancia-ollama.com ou http://IP:11434)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", None)

    # Humanização da resposta simbólica (symbolic_kg): se ativada, a resposta
    # determinística do Knowledge Graph passa por um LLM que APENAS suaviza o
    # tom, preservando todos os fatos. Padrão DESLIGADO para manter a garantia
    # "sem LLM / 0% alucinação" nos experimentos do paper. Ative no app/produção
    # com FESPAI_HUMANIZE_KG=1.
    HUMANIZE_KG = os.getenv("FESPAI_HUMANIZE_KG", "0") == "1"
    
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

