#!/usr/bin/env python3
import warnings
import os
from typing import List, Optional
from datetime import datetime
from uuid import uuid4

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .rag import RAGUnifesp

app = FastAPI(title="FESP-AI API", version="0.1.0")

cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://frontend:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = None
conversations: dict[str, List[dict]] = {}


class Message(BaseModel):
    role: str  # "user" ou "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    include_history: bool = True
    max_history: int = 10  # Número máximo de mensagens anteriores a incluir


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: List[Message]


@app.on_event("startup")
async def startup_event():
    import threading
    global rag
    print("Inicializando RAG...")
    rag = RAGUnifesp()
    rag.sync()
    print("RAG inicializado e pronto!")
    
    def warmup_models():
        import time
        import requests
        time.sleep(1)
        print("Pre-carregando modelos (warmup)...")
        try:
            ollama_url = rag.config.OLLAMA_BASE_URL or "http://ollama:11434"
            print(f"  - Carregando modelo LLM: {rag.config.MODEL_NAME}")
            requests.post(f"{ollama_url}/api/generate", json={
                "model": rag.config.MODEL_NAME,
                "prompt": "teste",
                "stream": False,
                "keep_alive": "5m"
            }, timeout=60)
            print(f"  - Carregando modelo embeddings: {rag.config.EMBEDDING_MODEL}")
            requests.post(f"{ollama_url}/api/embed", json={
                "model": rag.config.EMBEDDING_MODEL,
                "input": "teste",
                "keep_alive": "5m"
            }, timeout=60)
            print("Modelos pre-carregados! Primeira query sera mais rapida.")
        except Exception as e:
            print(f"Warmup falhou: {e}")
    
    threading.Thread(target=warmup_models, daemon=True).start()


@app.get("/")
async def root():
    return {
        "message": "FESP-AI API",
        "status": "running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    return {"status": "healthy", "rag_ready": rag.chain is not None}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    
    conversation_id = request.conversation_id or str(uuid4())
    
    if conversation_id not in conversations:
        conversations[conversation_id] = []
    
    user_message = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    }
    conversations[conversation_id].append(user_message)
    
    if request.include_history and len(conversations[conversation_id]) > 1:
        history = conversations[conversation_id][-request.max_history-1:-1]
        context_messages = "\n\n".join([
            f"{'Usuario' if msg['role'] == 'user' else 'Assistente'}: {msg['content']}"
            for msg in history
        ])
        
        enhanced_question = f"""Contexto da conversa anterior:
{context_messages}

Pergunta atual: {request.message}

Responda considerando o contexto da conversa anterior."""
    else:
        enhanced_question = request.message
    
    try:
        response_text = rag.query(enhanced_question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {str(e)}")
    
    assistant_message = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat()
    }
    conversations[conversation_id].append(assistant_message)
    
    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        timestamp=assistant_message["timestamp"]
    )


@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")
    
    messages = [
        Message(**msg) for msg in conversations[conversation_id]
    ]
    
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=messages
    )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")
    
    del conversations[conversation_id]
    return {"message": "Conversa deletada com sucesso"}


@app.post("/conversations")
async def create_conversation():
    conversation_id = str(uuid4())
    conversations[conversation_id] = []
    return {"conversation_id": conversation_id}


@app.get("/status")
async def status():
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    
    counts = rag.list_sources()
    return {
        "rag_ready": rag.chain is not None,
        "sources": counts,
        "active_conversations": len(conversations),
        "total_messages": sum(len(msgs) for msgs in conversations.values())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

