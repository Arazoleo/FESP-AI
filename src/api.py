#!/usr/bin/env python3
import warnings
import os
import re
import logging
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Expandir pergunta contextual se necessário
        message_lower = request.message.lower().strip()
        enhanced_question = request.message
        
        # 1. Resolver referências pronominais (dele, dela, ele, ela, etc.)
        pronome_patterns = [
            r'\b(?:dele|dela|desse|dessa|do professor|da professora|desse docente|dessa docente)\b',
            r'\ba área (?:dele|dela)\b',
            r'\b(?:sobre|com)\s+(?:ele|ela)\b',  # "sobre ele", "com ele", "contato com ele"
        ]
        has_pronome = any(re.search(p, message_lower) for p in pronome_patterns)
        
        if has_pronome:
            # Procurar nome de docente mencionado na conversa
            docente_encontrado = None
            
            # PRIORIDADE 0: Nome na própria pergunta atual (ex: "IC com o Álvaro, qual a área dele?")
            docente_match_atual = re.search(
                r'(?:com\s+o|com\s+a|do|da)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                request.message
            )
            if docente_match_atual:
                docente_encontrado = docente_match_atual.group(1)
            
            # PRIORIDADE 1: Se não encontrou na pergunta atual, procurar em perguntas do usuário no histórico
            if not docente_encontrado:
                for msg in reversed(history):
                    if msg['role'] == 'user':
                        content = msg['content']
                        # "com o Álvaro Fazenda", "do Álvaro Fazenda"
                        docente_match = re.search(
                            r'(?:com\s+o|com\s+a|do|da)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                            content
                        )
                        if docente_match:
                            docente_encontrado = docente_match.group(1)
                            break
            
            # PRIORIDADE 2: Se não encontrou em perguntas, procurar em respostas do sistema
            if not docente_encontrado:
                for msg in reversed(history):
                    if msg['role'] == 'assistant':
                        content = msg['content']
                        
                        # "X é especialista" ou "X leciona"
                        nome_match = re.search(
                            r'^([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)\s+(?:é\s+especialista|leciona)',
                            content
                        )
                        if nome_match:
                            docente_encontrado = nome_match.group(1)
                            break
                        
                        # "O professor X é especialista"
                        prof_match = re.search(
                            r'(?:O\s+)?[Pp]rofessor(?:a)?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                            content
                        )
                        if prof_match:
                            docente_encontrado = prof_match.group(1)
                            break
                        
                        # "são X e Y" ou "são: X, Y" - pegar o primeiro nome
                        sao_match = re.search(
                            r'são:?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                            content
                        )
                        if sao_match:
                            docente_encontrado = sao_match.group(1)
                            break
                        
                        # Lista com "- Nome" (ex: "- Daniela Leal Musa")
                        lista_match = re.search(
                            r'^-\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
                            content,
                            re.MULTILINE
                        )
                        if lista_match:
                            docente_encontrado = lista_match.group(1)
                            break
            
            if docente_encontrado:
                # Substituir referência pronominal pelo nome do docente
                for pronome in ['com ele', 'com ela', 'dele', 'dela', 'desse professor', 'da professora', 'desse docente', 'dessa docente']:
                    if pronome in message_lower:
                        if pronome in ['com ele', 'com ela']:
                            enhanced_question = re.sub(
                                rf'\b{pronome}\b',
                                f'com o professor {docente_encontrado}',
                                enhanced_question,
                                flags=re.IGNORECASE
                            )
                        else:
                            enhanced_question = re.sub(
                                rf'\b{pronome}\b',
                                f'do professor {docente_encontrado}',
                                enhanced_question,
                                flags=re.IGNORECASE
                            )
                        break
                logger.info(f"[CONTEXTO] Referência pronominal resolvida: '{request.message}' -> '{enhanced_question}'")
        
        # 2. Resolver referências a "essa disciplina", "essa matéria", etc.
        disciplina_refs = ['essa disciplina', 'essa matéria', 'essa cadeira', 'a disciplina', 'a matéria']
        if not has_pronome and any(ref in message_lower for ref in disciplina_refs):
            # Procurar nome de disciplina mencionada anteriormente
            disciplina_encontrada = None
            for msg in reversed(history):
                content = msg['content']
                # Perguntas do usuário sobre disciplinas
                if msg['role'] == 'user':
                    disc_match = re.search(
                        r'(?:pré-?requisitos?\s+(?:de|da|do)|disciplinas?\s+(?:de|da|do)|professore?s?\s+(?:de|da|do|que\s+d[aã]o))\s+(.+?)(?:\?|$)',
                        content,
                        re.IGNORECASE
                    )
                    if disc_match:
                        disciplina_encontrada = disc_match.group(1).strip()
                        break
            
            if disciplina_encontrada:
                for ref in disciplina_refs:
                    if ref in message_lower:
                        enhanced_question = re.sub(
                            rf'\b{ref}\b',
                            disciplina_encontrada,
                            enhanced_question,
                            flags=re.IGNORECASE
                        )
                        break
                logger.info(f"[CONTEXTO] Referência a disciplina resolvida: '{request.message}' -> '{enhanced_question}'")
        
        # 3. Expandir perguntas curtas sobre termos (ex: "e as do termo 5?")
        elif len(request.message.split()) < 10 and any(word in message_lower for word in ['e as', 'e o', 'e do']):
            # Pegar a última pergunta do usuário
            last_user_question = None
            for msg in reversed(history):
                if msg['role'] == 'user':
                    last_user_question = msg['content']
                    break
            
            if last_user_question:
                # Detectar número de termo na pergunta atual
                termo_match = re.search(r'termo\s+(\d+)', message_lower)
                if termo_match:
                    novo_termo = termo_match.group(1)
                    # Substituir termo na pergunta anterior
                    expanded = re.sub(r'termo\s+\d+', f'termo {novo_termo}', last_user_question, flags=re.IGNORECASE)
                    enhanced_question = expanded
                    logger.info(f"[CONTEXTO] Pergunta expandida: '{request.message}' -> '{enhanced_question}'")
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

