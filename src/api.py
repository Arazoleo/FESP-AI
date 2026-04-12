#!/usr/bin/env python3
import warnings
import os
import re
import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import OrderedDict
from uuid import uuid4

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
except ImportError:
    pass

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .multi_agent_rag import MultiAgentRAG
from .context_resolver import context_resolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FESP-AI API", version="0.1.0")

cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://frontend:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag: MultiAgentRAG = None

# Configurações de gerenciamento de memória para conversas
MAX_CONVERSATIONS = 1000  # Máximo de conversas simultâneas
CONVERSATION_TTL = timedelta(hours=24)  # Tempo de vida das conversas

# Usar OrderedDict para manter ordem de inserção (LRU)
conversations: OrderedDict[str, List[dict]] = OrderedDict()
conversation_timestamps: Dict[str, datetime] = {}


def cleanup_old_conversations():
    """Remove conversas antigas e limita o número total de conversas."""
    now = datetime.now()
    
    # Remover conversas expiradas
    expired = [
        cid for cid, ts in conversation_timestamps.items()
        if now - ts > CONVERSATION_TTL
    ]
    for cid in expired:
        conversations.pop(cid, None)
        conversation_timestamps.pop(cid, None)
    
    # Limitar número máximo (remover mais antigas - LRU)
    while len(conversations) > MAX_CONVERSATIONS:
        oldest_cid, _ = conversations.popitem(last=False)
        conversation_timestamps.pop(oldest_cid, None)
    
    if expired:
        logger.info(f"[CLEANUP] Removidas {len(expired)} conversas expiradas. Total: {len(conversations)}")


class Message(BaseModel):
    role: str  # "user" ou "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    include_history: bool = True
    max_history: int = 10  # Número máximo de mensagens anteriores a incluir


class AgentInfo(BaseModel):
    label: str
    description: str
    color: str
    icon: str


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str
    active_agent: str = "fallback"
    agent_info: Optional[AgentInfo] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: List[Message]


@app.on_event("startup")
async def startup_event():
    import threading
    global rag
    print("Inicializando Multi-Agent RAG...")
    rag = MultiAgentRAG()
    rag.sync()
    print("Multi-Agent RAG inicializado e pronto!")
    
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
    return {
        "status": "healthy",
        "rag_ready": rag.chain is not None,
        "multi_agent": rag._pipeline is not None,
        "model": rag.config.MODEL_NAME,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    
    conversation_id = request.conversation_id or str(uuid4())
    
    # Limpar conversas antigas periodicamente
    cleanup_old_conversations()
    
    if conversation_id not in conversations:
        conversations[conversation_id] = []
        conversation_timestamps[conversation_id] = datetime.now()
    else:
        # Atualizar timestamp (mover para final - LRU)
        conversations.move_to_end(conversation_id)
        conversation_timestamps[conversation_id] = datetime.now()
    
    user_message = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    }
    conversations[conversation_id].append(user_message)
    
    # Usar o ContextResolver para resolver referências contextuais
    if request.include_history and len(conversations[conversation_id]) > 1:
        history = conversations[conversation_id][-request.max_history-1:-1]
        
        # Atualizar contexto com mensagens do histórico
        for msg in history:
            context_resolver.update_context(conversation_id, msg['content'], msg['role'])
        
        # Resolver referências na pergunta atual (baseado em regras)
        enhanced_question, was_modified = context_resolver.resolve_question(
            request.message, 
            conversation_id, 
            history
        )
        
        # Se não foi modificado mas a pergunta é ambígua, usar LLM
        if not was_modified and context_resolver.is_ambiguous_question(request.message):
            # Usar LLM para reescrever apenas se realmente necessário
            if rag and rag.llm:
                enhanced_question = context_resolver.rewrite_with_llm(
                    request.message,
                    conversation_id,
                    history,
                    rag.llm
                )
                if enhanced_question != request.message:
                    was_modified = True
        
        if was_modified:
            logger.info(f"[CONTEXT] Pergunta resolvida: '{request.message}' → '{enhanced_question}'")
    else:
        enhanced_question = request.message
    
    # Atualizar contexto com a pergunta atual
    context_resolver.update_context(conversation_id, request.message, 'user')
    
    try:
        result = rag.query_with_metadata(enhanced_question)
        response_text = result["response"]
        active_agent = result.get("active_agent", "fallback")
        agent_metadata = result.get("agent_info") or result.get("agent_metadata", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {str(e)}")
    
    assistant_message = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat()
    }
    conversations[conversation_id].append(assistant_message)
    
    # Atualizar contexto com a resposta (para extrair listas de docentes, etc.)
    context_resolver.update_context(conversation_id, response_text, 'assistant')
    
    logger.info(f"[AGENT] Agente ativo: {active_agent}")
    
    agent_info = None
    if agent_metadata:
        agent_info = AgentInfo(
            label=agent_metadata.get("label", active_agent),
            description=agent_metadata.get("description", ""),
            color=agent_metadata.get("color", "#6b7280"),
            icon=agent_metadata.get("icon", "Bot"),
        )
    
    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        timestamp=assistant_message["timestamp"],
        active_agent=active_agent,
        agent_info=agent_info,
    )


class BaselineRequest(BaseModel):
    message: str
    system: str = "b2"  # "b2" = Standard RAG | "b3" = Graph-RAG sem validação


class BaselineResponse(BaseModel):
    response: str
    system: str
    latency_s: float


@app.post("/chat_baseline", response_model=BaselineResponse)
async def chat_baseline(request: BaselineRequest):
    """
    Endpoint para avaliação dos baselines do paper BRACIS.
    
    system="b2" → Standard RAG (só vector store, sem KG, sem validação simbólica)
    system="b3" → Graph-RAG (KG + vector store, sem validação neurossimbólica)
    """
    import time
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    if request.system not in ("b2", "b3"):
        raise HTTPException(status_code=400, detail="system deve ser 'b2' ou 'b3'")

    PROMPT = (
        "Você é um assistente acadêmico da UNIFESP ICT. Responda APENAS em português "
        "brasileiro usando SOMENTE as informações abaixo. Se não encontrar, diga que "
        "não tem a informação.\n\n"
        "{context}\n\nPergunta: {question}\n\nResposta:"
    )
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | rag.llm | StrOutputParser()

    t0 = time.time()
    try:
        inner = rag._rag  # RAGUnifesp instance (MultiAgentRAG wraps it)
        if request.system == "b2":
            # Só retriever híbrido, sem KG
            docs = inner.retriever.invoke(request.message)
            context = inner._format_docs(docs)
        else:
            # B3: KG + retriever, sem enriquecimento/validação simbólica
            context_parts = []
            if inner.graph_rag:
                use_g, q_type, termo = inner.graph_rag.should_use_graph(request.message)
                if use_g and q_type and termo:
                    kg_resp = inner.graph_rag.query_graph(q_type, termo)
                    if kg_resp:
                        context_parts.append(kg_resp)
            docs = inner.retriever.invoke(request.message)
            context_parts.append(inner._format_docs(docs))
            context = "\n\n".join(context_parts)

        response = chain.invoke({"context": context, "question": request.message})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return BaselineResponse(
        response=response.strip(),
        system=request.system,
        latency_s=round(time.time() - t0, 2),
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
    context_resolver.clear_context(conversation_id)
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


# ==================== ENDPOINTS DE EXTRAÇÃO DE RELAÇÕES ====================

class ExtractRequest(BaseModel):
    text: str
    min_confidence: float = 0.6


class EnrichRequest(BaseModel):
    text: str
    min_confidence: float = 0.7


@app.post("/extract-relations")
async def extract_relations(request: ExtractRequest):
    """
    Extrai relações de um texto sem adicionar ao grafo.
    Útil para preview antes de enriquecer o Knowledge Graph.
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG não inicializado")
    
    if not rag.relation_extractor:
        raise HTTPException(status_code=503, detail="Extrator de relações não disponível")
    
    try:
        relations = rag.extract_relations(request.text, request.min_confidence)
        return {
            "relations": relations,
            "count": len(relations),
            "text_length": len(request.text)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@app.post("/enrich-graph")
async def enrich_graph(request: EnrichRequest):
    """
    Extrai relações de um texto e adiciona ao Knowledge Graph.
    Requer maior confiança por padrão (0.7).
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG não inicializado")
    
    if not rag.graph_enricher:
        raise HTTPException(status_code=503, detail="Enriquecedor de grafo não disponível")
    
    try:
        stats = rag.enrich_graph_from_text(request.text, request.min_confidence)
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no enriquecimento: {str(e)}")


@app.get("/graph-stats")
async def graph_stats():
    """Retorna estatísticas do Knowledge Graph."""
    if rag is None or not rag.knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph não disponível")
    
    stats = rag.knowledge_graph.get_stats()
    
    # Adicionar estatísticas de extração se disponíveis
    if rag.graph_enricher:
        extraction_stats = rag.graph_enricher.get_extraction_stats()
        stats['extracted_relations'] = extraction_stats
    
    return stats


@app.get("/graph")
async def get_graph():
    """Retorna o Knowledge Graph completo para visualização (nodes + edges)."""
    if rag is None or not rag.knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph não disponível")
    return rag.knowledge_graph.export_for_visualization()


@app.get("/graph-viewer")
async def graph_viewer_page():
    """Serve a página HTML que visualiza o grafo (mesma origem que /graph, evita CORS)."""
    path = Path(__file__).resolve().parent.parent / "graph_viewer.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="graph_viewer.html não encontrado")
    return FileResponse(path, media_type="text/html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

